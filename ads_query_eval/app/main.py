from email.headerregistry import Address
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import smtplib
import ssl


import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Form, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jinja2 import Environment, PackageLoader, select_autoescape
from starlette import status
from starlette.responses import HTMLResponse, RedirectResponse
from toolz import assoc

from ads_query_eval.app import bootstrap
from ads_query_eval.config import (
    get_terminus_client,
    SITE_URL,
    get_smtp_config,
    get_invite_link_credentials,
)
from ads_query_eval.lib.io import find_one
from ads_query_eval.lib.util import get_password_hash

security = HTTPBasic()
app = FastAPI()

jinja_env = Environment(
    loader=PackageLoader("ads_query_eval", "app/templates"),
    autoescape=select_autoescape(),
)


@app.on_event("startup")
def _bootstrap():
    bootstrap.bootstrap()


@app.get("/invite_link/new")
def new_invite_link(credentials: HTTPBasicCredentials = Depends(security)):
    username, password = get_invite_link_credentials()
    correct_username = secrets.compare_digest(credentials.username, username)
    correct_password = secrets.compare_digest(credentials.password, password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    token = secrets.token_urlsafe()
    client = get_terminus_client()
    client.insert_document(
        {
            "@type": "InviteLink",
            "token": token,
        }
    )
    return RedirectResponse(SITE_URL + f"/invite_link/{token}")


@app.get("/invite_link/{token}")
def invite_link(token: str):
    client = get_terminus_client()
    valid = bool(list(client.query_document({"@type": "InviteLink", "token": token})))
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite link.",
        )
    return HTMLResponse(
        content=jinja_env.get_template("credentials_request.jinja2").render(
            invite_link_token=token
        ),
        status_code=200,
    )


@app.post("/credentials_request")
def invite_link(email_address: str = Form(...), invite_link_token: str = Form(...)):
    client = get_terminus_client()
    invite_link_doc = find_one(
        client, {"@type": "InviteLink", "token": invite_link_token}
    )
    if invite_link_doc is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite link token"
        )
    [id_credentials_request] = client.insert_document(
        {
            "@type": "CredentialsRequest",
            "email_address": email_address,
            "invite_link": invite_link_doc["@id"],
        }
    )
    password = secrets.token_hex()
    print(password)
    hashed_password = get_password_hash(password)

    user = find_one(client, {"@type": "User", "email_address": email_address})
    if user:
        # If user exists, reset password.
        client.update_document(assoc(user, "hashed_password", hashed_password))
    else:
        # Otherwise, create new user and set username and password.
        user = {
            "@type": "User",
            "email_address": email_address,
            "username": secrets.token_hex(),
            "hashed_password": hashed_password,
        }
        [id_user] = client.insert_document(user)
        user["@id"] = id_user

    rv = requests.post(
        "http://snappass:5000/",
        data={
            "ttl": "hour",
            "password": f"username:\n{user['username']}\npassword:\n{password}",
        },
    )
    soup = BeautifulSoup(rv.text, "html.parser")
    one_time_link = soup.find(id="password-link").get("value")
    email_credentials_link(receiver_email=email_address, one_time_link=one_time_link)
    client.insert_document(
        {
            "@type": "EmailedCredentialsLink",
            "one_time_link": one_time_link,
            "credentials_request": id_credentials_request,
            "user": user["@id"],
        }
    )
    return HTMLResponse(
        content=jinja_env.get_template(
            "credentials_request_confirmation.jinja2"
        ).render(email_address=email_address),
        status_code=200,
    )


@app.get("/")
def all_queries():
    client = get_terminus_client()
    queries = list(client.get_documents_by_type("Query"))
    for q in queries:
        q["id"] = q["@id"].split("/", maxsplit=1)[1]

    template = jinja_env.get_template("queries.jinja2")
    html_content = template.render(
        summary_of_all_queries=f"There are {len(queries)} queries.",
        queries=queries,
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/queries/{query_literal}")
def query_retrievals(query_literal: str):
    client = get_terminus_client()
    query = list(
        client.query_document({"@type": "Query", "query_literal": query_literal})
    )
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="query not found"
        )
    query = query[0]
    retrievals = list(
        client.query_document({"@type": "Retrieval", "query": query["@id"]})
    )
    print(retrievals)
    template = jinja_env.get_template("retrievals.jinja2")
    html_content = template.render(
        summary_of_all_query_runs=(
            f"This is for a summary of all retrievals of Query {query_literal} "
            "and their evaluations."
        ),
        query={"query_literal": query_literal},
        runs=sorted(retrievals, key=lambda r: r["done_at"], reverse=True),
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


def email_credentials_link(receiver_email: str, one_time_link: str):
    smtp_config = get_smtp_config()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Credentials for {SITE_URL}"
    msg["From"] = smtp_config["from_addr"]
    msg["To"] = receiver_email
    msg.attach(
        MIMEText(
            jinja_env.get_template("credentials_link_email.txt.jinja2").render(
                one_time_link=one_time_link, site_url=SITE_URL
            ),
            "plain",
        )
    )
    msg.attach(
        MIMEText(
            jinja_env.get_template("credentials_link_email.html.jinja2").render(
                one_time_link=one_time_link, site_url=SITE_URL
            ),
            "html",
        )
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        host=smtp_config["host"], port=smtp_config["port"], context=context
    ) as server:
        server.login(user=smtp_config["user"], password=smtp_config["password"])
        server.sendmail(
            from_addr=smtp_config["from_addr"],
            to_addrs=receiver_email,
            msg=msg.as_string(),
        )
