import gzip
import json
import pickle

from dagster import (
    op,
    repository,
    resource,
    graph,
    OpExecutionContext,
    DynamicOut,
    DynamicOutput,
    io_manager,
    IOManager,
)
from gridfs import GridFS

from ads_query_eval.bootstrap import bootstrap
from ads_query_eval.config import get_mongo_db
from ads_query_eval.lib.fetch import fetch_first_n

from ads_query_eval.lib.io import gfs_put_as_gzipped_json, fetch_first_page
from ads_query_eval.models import Query

bootstrap()


@resource
def mongo_db():
    return get_mongo_db()


@resource
def mongo_gfs():
    return GridFS(get_mongo_db())


class MongoGFSIOManager(IOManager):
    def __init__(self):
        self.gfs = GridFS(get_mongo_db())

    def handle_output(self, context, obj):
        filename = "__".join(context.get_identifier())
        self.gfs.put(pickle.dumps(obj), filename=filename)

    def load_input(self, context):
        filename = "__".join(context.get_identifier())
        return pickle.loads(self.gfs.get_last_version(filename=filename).read())


@io_manager
def mongo_gfs_io_manager():
    return MongoGFSIOManager()


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
    db = get_mongo_db()
    queries = [Query(**d) for d in db.queries.find()]
    jobs = []
    for q in queries:
        common_op_config = {"query": q.query, "query_id": q.id}
        jobs.append(
            get_and_log_query_results.to_job(
                name=f"get_and_log_query_{q.id:02}_results",
                resource_defs={
                    "db": mongo_db,
                    "gfs": mongo_gfs,
                    "io_manager": mongo_gfs_io_manager,
                },
                config={
                    "ops": {
                        "get_query_responses": {"config": common_op_config},
                        "query_responses_to_analysis_dict": {
                            "config": common_op_config
                        },
                    }
                },
            )
        )

    return jobs
