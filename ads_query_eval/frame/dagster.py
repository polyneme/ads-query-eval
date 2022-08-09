import pickle

from dagster import (
    op,
    repository,
    resource,
    graph,
    OpExecutionContext,
    io_manager,
    IOManager,
    SourceAsset,
    AssetKey,
    asset,
    AssetIn,
    define_asset_job,
    ScheduleDefinition,
    with_resources,
    static_partitioned_config,
    job,
    schedule,
)
from gridfs import GridFS

from ads_query_eval.app.bootstrap import bootstrap
from ads_query_eval.config import get_s3_client, get_terminus_client
from ads_query_eval.lib.io import fetch_first_n

from ads_query_eval.frame import s3
from ads_query_eval.lib.io import gfs_put_as_gzipped_json, fetch_first_page
from ads_query_eval.frame.models import Query
from ads_query_eval.lib.util import hash_of

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
        s3.put(key=key, body=pickle.dumps(obj))

    def load_input(self, context):
        key = "__".join(context.get_identifier())
        return pickle.loads(s3.get(key=key).read())


@io_manager
def s3_pickle_io_manager():
    return S3PickleIOManager()


@op(config_schema={"query": str, "query_id": str}, required_resource_keys={"db"})
def get_query_responses(context: OpExecutionContext):
    doc = context.resources.db.queries.find_one({"query": context.op_config["query"]})
    q = Query(**doc)
    if q.id != context.op_config["query_id"]:
        raise ValueError("Mismatch between supplied and retrieved query id")

    context.log.info(f"fetching {q.query}")
    responses = fetch_first_n(q=q.query, n=1000, logger=context.log)
    return {"payload": responses, "name": f"query_{q.id:02}_responses"}


@op(config_schema={"query": str, "query_id": str})
def query_responses_to_analysis_dict(context: OpExecutionContext, responses: list):
    query_analysis = {}
    query_id = context.op_config["query_id"]

    for r in responses:
        highlighting = r["highlighting"]
        q = r["responseHeader"]["params"]["q"]
        docs = r["response"]["docs"]
        docs_with_highlighting = []
        for d in docs:
            dwh = {k: v for k, v in d.items()}
            h_for_doc = highlighting.get(d["id"])
            if h_for_doc:
                dwh["highlighting"] = h_for_doc
            docs_with_highlighting.append(dwh)
        if q not in query_analysis:
            query_analysis[q] = {"returned": []}
        query_analysis[q]["returned"].extend(docs_with_highlighting)
    return {"payload": query_analysis, "name": f"query_analysis"}


@op(required_resource_keys={"gfs"})
def persist_to_gfs(context: OpExecutionContext, named_payload):
    payload, basename = named_payload["payload"], named_payload["name"]
    _id = gfs_put_as_gzipped_json(context.resources.gfs, payload, basename)
    context.log.info(f"results logged as {basename}.json.gz ({_id}) in GridFS")
    return str(_id)


@op(required_resource_keys={"db"})
def register_query_run_id(context: OpExecutionContext, run_id: str):
    db = context.resources.db
    db.queries.update_one()


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


@graph
def get_and_log_query_results():
    responses = get_query_responses()
    persist_to_gfs(responses)

    query_analysis = query_responses_to_analysis_dict(responses)
    persist_to_gfs(query_analysis)

    query_analysis = inject_topic_review_analysis(query_analysis)
    persist_to_gfs(query_analysis)


@repository
def default():
    client = get_terminus_client()
    queries = client.get_documents_by_type("Query", as_list=True)
    query_literals = [q["query_literal"] for q in queries]

    @static_partitioned_config(partition_keys=query_literals)
    def retrieval_config(partition_key: str):
        return {"ops": {"retrieval_op": {"config": {"query_literal": partition_key}}}}

    @op(config_schema={"query_literal": str}, required_resource_keys={"s3", "terminus"})
    def retrieval_op(context):
        q = context.op_config["query_literal"]
        context.log.info(q)
        # rv = fetch_first_n(q=q, n=1000, logger=context.log)

    @job(
        config=retrieval_config,
        resource_defs={"s3": s3_resource, "terminus": terminus_resource},
    )
    def retrieval_job():
        retrieval_op()

    @schedule(cron_schedule="0 0 * * *", job=retrieval_job)
    def retrieval_schedule():
        for q in query_literals:
            request = retrieval_job.run_request_for_partition(
                partition_key=q, run_key=hash_of(q)
            )
            yield request

    return [retrieval_schedule]
