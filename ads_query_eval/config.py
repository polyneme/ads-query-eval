import json
from functools import lru_cache
import os
from pathlib import Path

from terminusdb_client import WOQLClient

QUERY_BASE_URL = os.environ.get("ADS_API_QUERY_BASE_URL")

HEADERS = {
    "Accept": "application/json",
    "Content-type": "application/json",
    "Authorization": f"Bearer {os.getenv('ADS_API_TOKEN')}",
}


@lru_cache()
def get_terminus_config():
    with (Path(__file__).resolve().parent / "frame" / "terminus.json").open() as f:
        schema_objects = json.load(f)
    return {
        "server_url": os.environ.get("TERMINUSDB_SERVER_URL", "http://localhost:6363/"),
        "admin_pass": os.environ.get("TERMINUSDB_ADMIN_PASS", "root"),
        "dbid": os.environ.get("TERMINUSDB_DBID", "ads-query-eval"),
        "schema_objects": schema_objects,
        "force_reset_on_init": os.environ.get("TERMINUSDB_FORCE_RESET"),
    }


@lru_cache
def get_terminus_client() -> WOQLClient:
    config = get_terminus_config()
    _client = WOQLClient(server_url=config["server_url"])
    _client.connect(db=config["dbid"], user="admin", key=config["admin_pass"])
    return _client
