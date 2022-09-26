import json
import pickle
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dagster import (
    op,
    repository,
    resource,
    OpExecutionContext,
    io_manager,
    IOManager,
    Failure,
    graph,
    ScheduleDefinition,
)
from toolz import assoc, merge
from terminusdb_client import WOQLQuery as WQ

from ads_query_eval.app.bootstrap import bootstrap
from ads_query_eval.config import get_s3_client, get_terminus_client
from ads_query_eval.frame.models import Retrieval
from ads_query_eval.lib.io import fetch_first_n, find_one

from ads_query_eval.frame import s3
from ads_query_eval.lib.io import fetch_first_page
from ads_query_eval.lib.util import now, today_as_str

bootstrap()


@resource
def s3_resource():
    return get_s3_client()


@resource
def terminus_resource():
    return get_terminus_client()


class S3PickleIOManager(IOManager):
    def handle_output(self, context, obj):
        key = "__".join(context.get_identifier())
        s3.put(client=get_s3_client(), key=key, body=pickle.dumps(obj))

    def load_input(self, context):
        key = "__".join(context.get_identifier())
        return pickle.loads(s3.get(client=get_s3_client(), key=key).read())


@io_manager
def s3_pickle_io_manager():
    return S3PickleIOManager()


@op(required_resource_keys={"db"})
def inject_topic_review_analysis(context: OpExecutionContext, query_analysis):
    query_topic_reviews = {
        d["query"]: d["bibcodes"]
        for d in context.resources.db.query_topic_reviews.find()
    }
    for q, a in query_analysis.items():
        context.log.info(f"{q}: {len(a['returned'])}")
        if "topic_review_info" not in a:
            a["topic_review_info"] = []
        for q_bibcode in query_topic_reviews[q]:
            print(f"fetching {q_bibcode} for {q}")
            a["topic_review_info"].append(fetch_first_page(q_bibcode))
    for q, a in query_analysis.items():
        a["relevant_bibcodes"] = set()
        for response in a["topic_review_info"]:
            a["relevant_bibcodes"] |= set(response["response"]["docs"][0]["reference"])
        a["relevant_bibcodes"] = list(a["relevant_bibcodes"])
    for q, a in query_analysis.items():
        for doc in a["returned"]:
            doc_bibcodes = set()
            doc_bibcodes.add(doc["bibcode"])
            doc_bibcodes |= set(
                doc["identifier"]
            )  # non-bibcodes don't affect intersection check below.
            doc["_relevant_as_topic_review_ref"] = bool(
                doc_bibcodes & set(a["relevant_bibcodes"])
            )
    return {"payload": query_analysis, "name": "query_analysis"}


def query_literal_to_dagster_name(s):
    return (
        s.replace(":", "_")
        .replace('"', "_")
        .replace(" ", "_")
        .replace("(", "_")
        .replace(")", "_")
        .replace(".", "_")
        .replace(",", "_")
    )


@repository
def default():
    client = get_terminus_client()
    queries = client.get_documents_by_type("Query", as_list=True)

    @op(
        config_schema={"query_literal": str, "date": str},
        required_resource_keys={"s3", "terminus"},
    )
    def retrieval_op(context: OpExecutionContext):
        need_to_format_retrieval = True
        s3_client, terminus_client = context.resources.s3, context.resources.terminus
        query_literal = context.op_config["query_literal"]
        q = next(
            terminus_client.query_document(
                {"@type": "Query", "query_literal": query_literal}
            ),
            None,
        )
        if q is None:
            raise Failure(f"No Query with query_literal {query_literal} found!")

        # get earlier date from config, else today
        today_str = today_as_str(tz=ZoneInfo("America/New_York"))
        date_str_from_config = context.op_config.get("date")
        if date_str_from_config:
            try:
                date.fromisoformat(date_str_from_config)
                if date_str_from_config > today_str:
                    raise Failure(
                        f"date given as config, '{date_str_from_config}', is in the future"
                    )
                yyyy_mm_dd = date_str_from_config
            except ValueError:
                raise Failure(
                    f"date given as config, '{date_str_from_config}', is invalid."
                )
        else:
            yyyy_mm_dd = today_str

        key = f"{query_literal}.{yyyy_mm_dd}.json.gz"
        completed_retrieval = find_one(
            terminus_client,
            {"@type": "Retrieval", "s3_key": key, "status": "completed"},
        )
        n_to_retrieve = 1000
        if completed_retrieval:
            context.log.info(f"Found metadata record for retrieval {key}")
            try:
                responses = s3.get_json(client=s3_client, key=key)
                context.log.info(f"Found retrieval data for {key}")
            except Exception as e:
                context.log.info(f"Exception info: {e}")
                context.log.info(f"Retrieval data for {key} not found. Will fetch.")
                responses = fetch_first_n(
                    q=query_literal, n=n_to_retrieve, logger=context.log
                )
                s3.put_json(client=s3_client, key=key, body=responses)
                context.log.info(f"Put {key} to S3")
            retrieval_id = completed_retrieval["@id"]
        else:
            context.log.info(
                f"Did not find metadata record for retrieval {key}. Checking for already-fetched data."
            )
            metadata_backfill = False
            try:
                responses = s3.get_json(client=s3_client, key=key)
                context.log.info(f"Found retrieval data for {key}")
                metadata_backfill = True
            except Exception as e:
                context.log.info(f"Exception info: {e}")
                context.log.info(f"Retrieval data for {key} not found. Will fetch.")
                responses = fetch_first_n(
                    q=query_literal, n=n_to_retrieve, logger=context.log
                )

            assigned_status = "completed"
            # TODO: save retrieval, then add another job step to take status to either
            #  'published' or 'unpublished' (along with (optional) 'reason' enum value 'same_as_prev').
            if not metadata_backfill:
                # Same as last retrieval? Then save status:aborted retrieval and do not persist data in S3.
                bindings = (
                    WQ()
                    .limit(1)
                    .order_by("v:done_at", order="desc")
                    .woql_and(
                        WQ().triple("v:retrieval", "type", "@schema:Retrieval"),
                        WQ().triple("v:retrieval", "query", q["@id"]),
                        WQ().triple("v:retrieval", "done_at", "v:done_at"),
                        WQ().triple("v:retrieval", "s3_key", "v:s3_key"),
                    )
                    .execute(terminus_client)["bindings"]
                )
                if bindings:
                    last_retrieval_metadata = bindings[0]
                    try:
                        last_retrieval_responses = s3.get_json(
                            client=s3_client,
                            key=last_retrieval_metadata["s3_key"]["@value"],
                        )
                        assigned_status = (
                            "aborted"
                            if (
                                json.dumps(responses, sort_keys=True)
                                == json.dumps(last_retrieval_responses, sort_keys=True)
                            )
                            else "completed"
                        )

                    except Exception as e:
                        context.log.info(f"Exception info: {e}")

            if assigned_status == "completed" and not metadata_backfill:
                s3.put_json(client=s3_client, key=key, body=responses)
                context.log.info(f"Put {key} to S3")
            doc = {
                "@type": "Retrieval",
                "query": q["@id"],
                "s3_key": key,
                "status": assigned_status,
                "items": [],
            }
            if assigned_status == "completed":
                doc = merge(
                    doc,
                    {
                        "done": "true",
                        "done_at": (
                            now()
                            if not metadata_backfill
                            else datetime.fromisoformat(yyyy_mm_dd)
                        ),
                    },
                )
            [retrieval_id] = terminus_client.insert_document(doc)
            need_to_format_retrieval = assigned_status == "completed"

        return {
            "retrieval": retrieval_id,
            "query_literal": query_literal,
            "responses": responses,
            "need_to_format_retrieval": need_to_format_retrieval,
        }

    @op(
        required_resource_keys={"terminus", "s3"},
    )
    def format_query_retrieval_for_evaluation(
        context: OpExecutionContext, retrieval_op_out
    ):
        if not retrieval_op_out["need_to_format_retrieval"]:
            context.log.info("no need to format retrieval")
            return

        s3_client, terminus_client = context.resources.s3, context.resources.terminus
        query_literal = retrieval_op_out["query_literal"]
        responses = retrieval_op_out["responses"]
        formatted_items = []
        context.log.info("formatting items")
        for r in responses:
            highlighting = r["highlighting"]
            q = r["responseHeader"]["params"]["q"]
            if q != query_literal:
                context.log.warning(
                    f"query param in retrieval ({q}) does not match query_literal {query_literal}"
                )
            docs = r["response"]["docs"]
            docs_with_highlighting = []
            for d in docs:
                dwh = {k: v for k, v in d.items()}
                h_for_doc = highlighting.get(d["id"])
                if h_for_doc:
                    dwh["highlighting"] = h_for_doc
                docs_with_highlighting.append(dwh)
            formatted_items.extend(docs_with_highlighting)

        _retrieval_doc = find_one(
            terminus_client,
            {"@type": "Retrieval", "@id": retrieval_op_out["retrieval"]},
        )
        context.log.info("updating retrieval with items")
        terminus_client.replace_document(
            assoc(
                _retrieval_doc,
                "items",
                [
                    {
                        "@type": "RetrievedItem",
                        "ads_bibcode": item["bibcode"],
                        "retrieval": retrieval_op_out["retrieval"],
                    }
                    for item in formatted_items
                ],
            ),
            commit_msg="updating retrieval with items",
        )
        _retrieval = Retrieval(**_retrieval_doc)
        s3.put_json(
            client=s3_client,
            key="items_all__" + _retrieval.s3_key,
            body=formatted_items,
        )
        s3.put_json(
            client=s3_client,
            key="items_top25__" + _retrieval.s3_key,
            body=formatted_items[:25],
        )

    @graph()
    def retrieval():
        format_query_retrieval_for_evaluation(retrieval_op())

    jobs = []
    schedule_jobs = []
    for i, q in enumerate(queries):
        job_name = "retrieval__" + query_literal_to_dagster_name(q["query_literal"])
        job = retrieval.to_job(
            name=job_name,
            resource_defs={"s3": s3_resource, "terminus": terminus_resource},
            config={
                "ops": {
                    "retrieval_op": {
                        "config": {"query_literal": q["query_literal"], "date": ""}
                    }
                }
            },
        )
        jobs.append(job)
        starthour = 10
        minutes_spacing = 2
        minutes_after_hour, hours_after_starthour = ((minutes_spacing * i) % 60), (
            (minutes_spacing * i) // 60
        )
        hours_after_midnight = starthour + hours_after_starthour
        assert hours_after_midnight < 24, "need to revisit job scheduling"
        schedule_jobs.append(
            ScheduleDefinition(
                name="daily__" + job.name,
                job=job,
                cron_schedule=f"{minutes_after_hour} {hours_after_midnight} * * *",
                execution_timezone="America/New_York",
            )
        )

    return [jobs + schedule_jobs]
