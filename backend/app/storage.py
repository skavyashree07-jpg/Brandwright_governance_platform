from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from minio import Minio
from minio.error import MinioException
from urllib3.exceptions import HTTPError

from app.config import settings


class StorageUnavailable(RuntimeError):
    pass


def _client() -> Minio:
    if not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
        raise RuntimeError("MinIO credentials must be configured before storing files.")
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
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
        client = _client()
        bucket = settings.MINIO_BUCKET
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        client.put_object(
            bucket,
            object_name,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type or "application/octet-stream",
        )
    except (MinioException, HTTPError) as exc:
        raise StorageUnavailable("The configured MinIO file store is unavailable.") from exc
    return object_name


def read_file(object_name: str) -> bytes:
    try:
        client = _client()
        response = client.get_object(settings.MINIO_BUCKET, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    except (MinioException, HTTPError) as exc:
        raise StorageUnavailable("The configured MinIO file store is unavailable.") from exc
