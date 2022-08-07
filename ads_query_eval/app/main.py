from fastapi import FastAPI
from jinja2 import Environment, PackageLoader, select_autoescape
from starlette.responses import HTMLResponse

from ads_query_eval.app import bootstrap
from ads_query_eval.config import get_terminus_client

app = FastAPI()

jinja_env = Environment(
    loader=PackageLoader("ads_query_eval", "app/templates"),
    autoescape=select_autoescape(),
)


@app.on_event("startup")
def _bootstrap():
    bootstrap.bootstrap()


@app.get("/")
def all_queries():
    client = get_terminus_client()
    template = jinja_env.get_template("queries.jinja2")
    queries = list(client.get_documents_by_type("Query"))
    for q in queries:
        q["id"] = q["@id"].split("/", maxsplit=1)[1]
    html_content = template.render(
        summary_of_all_queries=(
            "This is where summary information on all queries, their runs, "
            "and their evaluation, is presented."
        ),
        queries=queries,
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/queries/{query_id}")
def query_runs(query_id: int):
    template = jinja_env.get_template("runs.jinja2")
    html_content = template.render(
        summary_of_all_query_runs=(
            f"This is for a summary of all runs of Query {query_id} "
            "and their evaluations."
        ),
        query={"id": query_id},
        runs=sorted(queries[query_id]["runs"], key=lambda r: r["id"], reverse=True),
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/queries/{query_id}/runs/{run_id}")
def query_run_evals(query_id: int, run_id: int):
    template = jinja_env.get_template("run.jinja2")
    evals = []
    for r in queries[query_id]["runs"]:
        if r["id"] == run_id:
            evals = r["evals"]

    html_content = template.render(
        summary_of_all_query_run_evals=(
            f"This is for a summary of the evaluations thus far for "
            f"Run {run_id} of Query {query_id}."
        ),
        query={"id": query_id},
        run={"id": run_id},
        evals=evals,
    )
    return HTMLResponse(content=html_content, status_code=200)
