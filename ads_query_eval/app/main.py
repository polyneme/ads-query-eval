import json
from collections import defaultdict
from email.headerregistry import Address
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import smtplib
import ssl
from operator import itemgetter
from typing import List
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Form, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jinja2 import Environment, PackageLoader, select_autoescape
from starlette import status
from starlette.datastructures import FormData
from starlette.responses import HTMLResponse, RedirectResponse, JSONResponse
from terminusdb_client import WOQLQuery as WQ
from toolz import assoc, groupby

from ads_query_eval.app import bootstrap
from ads_query_eval.config import (
    get_terminus_client,
    SITE_URL,
    get_smtp_config,
    get_s3_client,
    get_invite_token,
    get_admins,
)
from ads_query_eval.frame import s3
from ads_query_eval.frame.models import (
    Retrieval,
    Query,
    RetrievedItem,
    ItemOfEvaluation,
    Evaluation,
    User,
    RetrievedItemContent,
)
from ads_query_eval.lib.io import find_one
from ads_query_eval.lib.util import get_password_hash, verify_password, now

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
def new_invite_link(via: str):
    if via != get_invite_token():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect token to get new invite-link",
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
def credentials_request(
    email_address: str = Form(...), invite_link_token: str = Form(...)
):
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


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    terminus_client = get_terminus_client()
    user = find_one(
        terminus_client, {"@type": "User", "username": credentials.username}
    )
    username = user["username"] if user else secrets.token_hex()
    hashed_password = (
        user["hashed_password"] if user else get_password_hash(secrets.token_hex())
    )
    correct_username = secrets.compare_digest(
        credentials.username or secrets.token_hex(), username
    )
    correct_password = verify_password(
        credentials.password or secrets.token_hex(), hashed_password
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/")
def all_queries():
    client = get_terminus_client()
    queries = [Query(**d) for d in client.get_documents_by_type("Query")]

    template = jinja_env.get_template("queries.jinja2")
    html_content = template.render(
        summary_of_all_queries=f"There are {len(queries)} queries.",
        queries=queries,
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/Query/{query_literal}")
def query_retrievals(query_literal: str):
    terminus_client = get_terminus_client()
    query = list(
        terminus_client.query_document(
            {"@type": "Query", "query_literal": query_literal}
        )
    )
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="query not found"
        )
    query = query[0]
    retrievals = [
        Retrieval(**r)
        for r in terminus_client.query_document(
            {"@type": "Retrieval", "query": query["@id"]}
        )
    ]
    n_retrieved = {}
    for r in retrievals:
        n_retrieved[r.id] = len(r.items)
    template = jinja_env.get_template("retrievals.jinja2")
    html_content = template.render(
        summary_of_all_query_retrievals=(
            f"There are {len(retrievals)} completed retrievals of Query {query_literal}."
        ),
        query={"query_literal": query_literal},
        retrievals=sorted(retrievals, key=lambda r: r.done_at, reverse=True),
        n_retrieved=n_retrieved,
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/Retrieval/{retrieval_id}")
def query_retrieval_evals(retrieval_id: str):
    terminus_client = get_terminus_client()
    rdoc = find_one(
        terminus_client,
        {"@type": "Retrieval", "s3_key": retrieval_id},
    )
    if rdoc is None:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"retrieval with ID Retrieval/{retrieval_id} not found",
        )
    retrieval = Retrieval(**rdoc)
    query = Query(
        **find_one(terminus_client, {"@type": "Query", "@id": retrieval.query})
    )
    evals = [
        Evaluation(**d)
        for d in terminus_client.query_document(
            {"@type": "Evaluation", "retrieval": retrieval.id, "done": "true"}
        )
    ]

    template = jinja_env.get_template("retrieval.jinja2")
    html_content = template.render(
        summary_of_all_query_retrieval_evals=(
            f"There have been {len(evals)} evaluations thus far for "
            f"this retrieval of Query {query.query_literal}."
        ),
        query=query,
        retrieval=retrieval,
        evals=evals,
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/Retrieval/{retrieval_id}/Evaluation")
def new_evaluation(retrieval_id: str, username: str = Depends(get_current_username)):
    s3_client = get_s3_client()
    terminus_client = get_terminus_client()
    user = User(**find_one(terminus_client, {"@type": "User", "username": username}))
    retrieval = Retrieval(
        **find_one(
            terminus_client,
            {"@type": "Retrieval", "@id": f"Retrieval/{quote(retrieval_id)}"},
        )
    )
    query = Query(
        **find_one(terminus_client, {"@type": "Query", "@id": retrieval.query})
    )
    [id_eval] = terminus_client.insert_document(
        {
            "@type": "Evaluation",
            "retrieval": retrieval.id,
            "evaluator": user.id,
            "status": "in progress",
            "done": False,
        }
    )
    items_content = s3.get_json(
        client=s3_client,
        key=retrieval.s3_key + "__items_top25",
    )
    id_eval = "/".join(id_eval.split("/")[-2:])
    items_for_evaluation = [
        {
            "@type": "ItemOfEvaluation",
            "evaluation": id_eval,
            "retrieved_item": i,
            "retrieved_item_content": RetrievedItemContent(**c),
        }
        for i, c in zip(retrieval.items, items_content)
    ]

    for i in items_for_evaluation:
        i["highlights"] = sorted(
            i["retrieved_item_content"].highlighting.items(),
            key=lambda pair: ("title", "abstract", "body", "ack").index(pair[0]),
        )
    template = jinja_env.get_template("eval_form.jinja2")
    html_content = template.render(
        id_eval=id_eval,
        query=query,
        retrieval=retrieval,
        items_for_evaluation=items_for_evaluation,
    )
    return HTMLResponse(content=html_content, status_code=200)


@app.post("/Evaluation/{eval_id}")
async def submit_evaluation(
    request: Request, eval_id: str, username: str = Depends(get_current_username)
):
    terminus_client = get_terminus_client()
    user = User(**find_one(terminus_client, {"@type": "User", "username": username}))
    form_data = await request.form()
    item_eval = defaultdict(dict)
    for k, v in form_data.items():
        if k.startswith("RetrievedItem/"):
            _, id_, prop = k.split("/")
            item_eval[id_][prop] = v

    eval = Evaluation(
        **find_one(
            terminus_client, {"@type": "Evaluation", "@id": f"Evaluation/{eval_id}"}
        )
    )
    docs = [
        {
            "@type": "ItemOfEvaluation",
            "evaluation": eval.id,
            "retrieved_item": f"RetrievedItem/{ri_id}",
            "relevance": inp.get("relevance", "not relevant"),
            "uncertainty": inp.get("uncertainty", "not supplied"),
            "evaluation_status": "done",
        }
        for ri_id, inp in item_eval.items()
    ]
    docs.append(
        {
            "@type": "Evaluation",
            "@id": eval.id,
            "done": "true",
            "status": "completed",
            "done_at": now(),
            "evaluator": user.id,
            "retrieval": eval.retrieval,
            "believed_query_intent": form_data.get("intent", ""),
        }
    )
    terminus_client.replace_document(docs, create=True)

    return RedirectResponse(
        url="/" + eval.retrieval, status_code=status.HTTP_303_SEE_OTHER
    )


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


@app.get("/user_completed_evals/")
def get_user_completed_evals(username: str = Depends(get_current_username)):
    terminus_client = get_terminus_client()
    user = User(**find_one(terminus_client, {"@type": "User", "username": username}))
    if user.email_address not in get_admins():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    return (
        WQ()
        .woql_and(
            WQ().triple("v:eval", "type", "@schema:Evaluation"),
            WQ().read_document("v:eval", "v:eval_doc"),
            WQ().triple("v:eval", "done", True),
            WQ().triple("v:eval", "evaluator", "v:evaluator"),
            WQ().triple("v:evaluator", "type", "@schema:User"),
            WQ().triple("v:evaluator", "email_address", "v:evaluator_email"),
            WQ().triple("v:eval", "retrieval", "v:retrieval"),
            WQ().triple("v:retrieval", "query", "v:query"),
            WQ().triple("v:query", "query_literal", "v:query_literal"),
            WQ().triple("v:itemofeval", "evaluation", "v:eval"),
            WQ().triple("v:itemofeval", "retrieved_item", "v:retrieveditem"),
            WQ().triple(
                "v:retrieveditem", "ads_bibcode", "v:retrieveditem_ads_bibcode"
            ),
            WQ().read_document("v:itemofeval", "v:itemofeval_doc"),
        )
        .execute(terminus_client)
    )


@app.get("/{cls}/")  # XXX This route must be last!
def get_documents_by_type(cls: str):
    terminus_client = get_terminus_client()
    if terminus_client.get_class_frame(cls):
        return terminus_client.get_documents_by_type(cls, as_list=True, count=25)
    return None
