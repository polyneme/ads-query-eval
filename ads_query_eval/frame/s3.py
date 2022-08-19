import json
from io import BytesIO
from typing import Dict, Any

from mypy_boto3_s3.client import S3Client, Exceptions

from ads_query_eval.config import get_s3_config

s3_config = get_s3_config()


def put(
    client: S3Client,
    key: str,
    body: bytes,
    acl: str = "private",
    metadata: Dict[str, str] = None,
):
    metadata = metadata or {}
    client.put_object(
        Bucket=s3_config["s3_bucket"],
        Key=(s3_config["s3_prefix"] + key),
        Body=body,
        ACL=acl,
        Metadata=metadata,
    )


def put_json(
    client: S3Client,
    key: str,
    body: Any,
    acl: str = "public-read",
    metadata: Dict[str, str] = None,
):
    try:
        body = json.dumps(body).encode("utf-8")
    except TypeError:
        raise TypeError(f"put_json: body given for key {key} is not JSON serializable")
    metadata = metadata or {}
    client.put_object(
        Bucket=s3_config["s3_bucket"],
        Key=(s3_config["s3_prefix"] + key),
        Body=body,
        ContentType="application/json",
        ContentEncoding="gzip",
        ACL=acl,
        Metadata=metadata,
    )


def get(client: S3Client, key: str) -> BytesIO:
    f = BytesIO()
    client.download_fileobj(s3_config["s3_bucket"], s3_config["s3_prefix"] + key, f)
    return f


def get_json(client: S3Client, key: str):
    return json.loads(get(client, key).getvalue())
