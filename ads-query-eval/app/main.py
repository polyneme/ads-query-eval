from typing import Union

from fastapi import FastAPI
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.responses import HTMLResponse

app = FastAPI()

jinja_env = Environment(
    loader=FileSystemLoader("app/templates"), autoescape=select_autoescape()
)

queries = {
    1: {
        "id": 1,
        "summary": "This query is doing well",
        "runs": [
            {
                "id": 2,
                "summary": (
                    "This query run happened an hour ago and no one has evaluated it yet, "
                    "but our M heuristic functions have run."
                ),
                "evals": [
                    {"id": 1, "summary": "heuristic function A says this."},
                    {"id": 2, "summary": "heuristic function B says this."},
                ],
            },
            {
                "id": 1,
                "summary": (
                    "This query run happened last week and was reviewed for relevance "
                    "by 3 people."
                ),
                "evals": [
                    {"id": 1, "summary": "ryan submitted this."},
                    {"id": 1, "summary": "edwin submitted this."},
                    {"id": 1, "summary": "brian submitted this."},
                ],
            },
        ],
    },
    2: {"id": 2, "summary": "This query needs attention", "runs": []},
}


@app.get("/")
def all_queries():
    template = jinja_env.get_template("queries.jinja2")
    html_content = template.render(
        summary_of_all_queries=(
            "This is where summary information on all queries, their runs, "
            "and their evaluation, is presented."
        ),
        queries=list(queries.values()),
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
