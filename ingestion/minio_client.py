"""
MinIO client wrapper using boto3.
S3-compatible — swap MINIO_ENDPOINT for real AWS S3 in production.
"""

import hashlib
import json
import logging
import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

BUCKET = os.getenv("MINIO_BUCKET", "mma-raw")


def get_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "mma_access"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "mma_secret123"),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def upload_json(client, key: str, data: dict) -> bool:
    """Upload dict as JSON. Returns True if uploaded, False if unchanged."""
    body     = json.dumps(data, indent=2, ensure_ascii=False).encode()
    new_hash = hashlib.sha256(body).hexdigest()

    try:
        head         = client.head_object(Bucket=BUCKET, Key=key)
        existing_hash = head.get("Metadata", {}).get("content-hash", "")
        if existing_hash == new_hash:
            return False
    except ClientError:
        pass

    client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
        Metadata={"content-hash": new_hash},
    )
    return True


def download_json(client, key: str) -> dict | None:
    try:
        resp = client.get_object(Bucket=BUCKET, Key=key)
        return json.loads(resp["Body"].read().decode())
    except ClientError:
        return None


def list_keys(client, prefix: str) -> list[str]:
    paginator = client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def event_key(event_id: str) -> str:
    return f"events/{event_id}.json"


def fight_key(event_id: str, fight_id: str) -> str:
    return f"fights/{event_id}/{fight_id}.json"
