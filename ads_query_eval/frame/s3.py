import json
from io import BytesIO
from typing import Dict

from ads_query_eval.config import get_s3_client, get_s3_config

s3_config = get_s3_config()


def put(key: str, body: bytes, acl: str = "private", metadata: Dict[str, str] = None):
    client = get_s3_client()
    metadata = metadata or {}
    client.put_object(
        Bucket=s3_config["s3_bucket"],
        Key=(s3_config["s3_prefix"] + key),
        Body=body,
        ACL=acl,
        Metadata=metadata,
    )


def get(key: str) -> BytesIO:
    client = get_s3_client()
    f = BytesIO()
    client.download_fileobj(s3_config["s3_bucket"], s3_config["s3_prefix"] + key, f)
    return f


def get_json(key: str):
    return json.load(get(key))
