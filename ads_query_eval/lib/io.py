import gzip
import json
from typing import Any
from urllib.parse import urlencode

import requests
from gridfs import GridFS

from ads_query_eval.config import QUERY_BASE_URL, HEADERS


def params_for(q=""):
    return {
        "__clearBigQuery": "true",
        "fl": (
            "identifier,[citations],reference,abstract,author,book_author,"
            "orcid_pub,orcid_user,orcid_other,bibcode,citation_count,"
            "comment,doi,id,keyword,page,property,pub,pub_raw,pubdate,pubnote,"
            "read_count,title,volume,links_data,esources,data,"
            "citation_count_norm,email,doctype"
        ),
        "q": q,
        "hl": "true",
        "hl.fl": "title,abstract,body,ack,*",
        "hl.maxAnalyzedChars": "150000",
        "hl.requireFieldMatch": "true",
        "hl.usePhraseHighlighter": "true",
        "rows": "25",
        "sort": "score desc",
        "start": "0",
    }


def fetch_first_page(q):
    encoded_query = urlencode(params_for(q))
    response = requests.get(f"{QUERY_BASE_URL}?{encoded_query}", headers=HEADERS)
    if response.status_code != 200:
        raise Exception(response.text)
    return response.json()


def fetch_first_n(q, n=1000, logger=None):
    responses = []
    n_fetched_total = 0
    start = 0
    rows = 200 if n > 200 else n
    while True:
        params = params_for(q)
        params["rows"] = str(rows)
        params["start"] = str(start)
        response = requests.get(
            f"{QUERY_BASE_URL}?{urlencode(params)}", headers=HEADERS
        )
        if response.status_code != 200:
            raise Exception(response.text)
        rv = response.json()
        responses.append(rv)
        n_fetched = len(rv["response"]["docs"])
        n_fetched_total += n_fetched
        if n_fetched_total >= n or n_fetched < rows:
            break
        else:
            start += rows
            if logger:
                logger.info(f"q: {q} start: {start}...")
    return responses


def gfs_put_as_gzipped_json(gfs: GridFS, payload: Any, basename=""):
    if not basename:
        raise ValueError("Need to supply basename")
    try:
        payload_str = json.dumps(payload)
    except TypeError:
        raise TypeError("payload isn't JSON serializable")

    data = gzip.compress(json.dumps(payload_str).encode("utf-8"))
    return gfs.put(data, filename=f"{basename}.json.gz")
