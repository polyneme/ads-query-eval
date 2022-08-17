import json
from io import BytesIO
from typing import Dict

from ads_query_eval.config import get_s3_config

s3_config = get_s3_config()


def put(
    client, key: str, body: bytes, acl: str = "private", metadata: Dict[str, str] = None
):
    metadata = metadata or {}
    client.put_object(
        Bucket=s3_config["s3_bucket"],
        Key=(s3_config["s3_prefix"] + key),
        Body=body,
        ACL=acl,
        Metadata=metadata,
    )


def get(client, key: str) -> BytesIO:
    f = BytesIO()
    client.download_fileobj(s3_config["s3_bucket"], s3_config["s3_prefix"] + key, f)
    return f


def get_json(client, key: str):
    return json.load(get(client, key))
