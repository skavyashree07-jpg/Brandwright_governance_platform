
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings


class StorageUnavailable(RuntimeError):
    pass


def _client():
    if not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
        raise RuntimeError("Supabase storage credentials must be configured.")

    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        region_name=settings.MINIO_REGION,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
    )


def store_file(
    organisation_id: str,
    collection: str,
    filename: str,
    data: bytes,
    content_type: str | None,
) -> str:
    safe_name = Path(filename).name.replace("/", "_").replace("\\", "_")
    object_name = f"{organisation_id}/{collection}/{uuid4()}-{safe_name}"

    try:
        _client().put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=object_name,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable(
            "The configured Supabase file store is unavailable."
        ) from exc

    return object_name


def read_file(object_name: str) -> bytes:
    try:
        response = _client().get_object(
            Bucket=settings.MINIO_BUCKET,
            Key=object_name,
        )
        return response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable(
            "The configured Supabase file store is unavailable."
        ) from exc
