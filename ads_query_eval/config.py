import json
from functools import lru_cache
import os
from pathlib import Path

import boto3
import requests
from tenacity import retry, wait_random_exponential
from terminusdb_client import WOQLClient

QUERY_BASE_URL = os.environ.get("ADS_API_QUERY_BASE_URL")

HEADERS = {
    "Accept": "application/json",
    "Content-type": "application/json",
    "Authorization": f"Bearer {os.getenv('ADS_API_TOKEN')}",
}

SITE_URL = os.environ.get("SITE_URL")


@lru_cache()
def get_terminus_config():
    with (Path(__file__).resolve().parent / "frame" / "terminus.json").open() as f:
        schema_objects = json.load(f)
    _config = {
        "server_url": os.environ.get("TERMINUSDB_SERVER_URL", "http://localhost:6363/"),
        "admin_pass": os.environ.get("TERMINUSDB_ADMIN_PASS", "root"),
        "dbid": os.environ.get("TERMINUSDB_DBID", "ads-query-eval"),
        "schema_objects": schema_objects,
        "force_reset_on_init": os.environ.get("TERMINUSDB_FORCE_RESET"),
    }

    @retry(wait=wait_random_exponential(multiplier=1, max=60))
    def health_check():
        print(f'Checking for 200 response from {_config["server_url"] + "api/info"}...')
        assert requests.get(_config["server_url"] + "api/info").status_code == 200

    health_check()
    return _config


@lru_cache
def get_terminus_client() -> WOQLClient:
    config = get_terminus_config()
    _client = WOQLClient(server_url=config["server_url"])
    _client.connect(db=config["dbid"], user="admin", key=config["admin_pass"])
    return _client


@lru_cache
def get_smtp_config():
    return {
        "host": os.environ.get("SMTP_HOST", "localhost"),
        "port": os.environ.get("SMTP_PORT", "465"),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "from_addr": os.environ.get("SMTP_FROM_ADDR"),
    }


@lru_cache
def get_s3_config():
    return {
        "s3_access_key_id": os.getenv("S3_ACCESS_KEY_ID"),
        "s3_secret_access_key": os.getenv("S3_SECRET_ACCESS_KEY"),
        "s3_region_name": os.getenv("S3_REGION_NAME"),
        "s3_endpoint_url": os.getenv("S3_ENDPOINT_URL"),
        "s3_bucket": os.getenv("S3_BUCKET"),
        "s3_prefix": os.getenv("S3_PREFIX"),
    }


def get_s3_client():
    # not using @lru_cache because:
    # "Session objects are not thread safe and should not be shared across threads and processes"
    _conf = get_s3_config()
    session = boto3.session.Session()
    return session.client(
        "s3",
        region_name=_conf["s3_region_name"],
        endpoint_url=_conf["s3_endpoint_url"],
        aws_access_key_id=_conf["s3_access_key_id"],
        aws_secret_access_key=_conf["s3_secret_access_key"],
    )
