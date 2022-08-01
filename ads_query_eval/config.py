from functools import lru_cache
import os

from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase

QUERY_BASE_URL = os.environ.get("ADS_API_QUERY_BASE_URL")

HEADERS = {
    "Accept": "application/json",
    "Content-type": "application/json",
    "Authorization": f"Bearer {os.getenv('ADS_API_TOKEN')}",
}


@lru_cache
def get_mongo_db() -> MongoDatabase:
    host = os.environ.get("MONGO_HOST", "mongo")
    dbname = os.environ.get("MONGO_DBNAME", "adsqe")
    _client = MongoClient(
        host=host,
        username=os.getenv("MONGO_USERNAME"),
        password=os.getenv("MONGO_PASSWORD"),
        connect=False,
    )
    return _client[dbname]
