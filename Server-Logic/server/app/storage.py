"""
storage.py — MinIO Object Storage Integration (Week 5)

Replaces the local-disk storage from Weeks 3-4 with MinIO bucket
operations via the boto3 S3-compatible client.

MinIO runs as a Docker container (see docker-compose.yml) and exposes
an S3-compatible API on port 9000.  This module wraps all storage
operations so the rest of the codebase never touches boto3 directly.

Environment variables (defaults match docker-compose.yml):
    MINIO_ENDPOINT   = http://localhost:9000
    MINIO_ACCESS_KEY = admin
    MINIO_SECRET_KEY = password
    MINIO_BUCKET     = shadowdrive
"""

import os
import io
import logging
import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "shadowdrive")


def _get_s3_client():
    """Create a boto3 S3 client configured for the local MinIO instance.

    signature_version='s3v4' and path-style access are required for MinIO
    compatibility — MinIO does not support virtual-hosted-style buckets.
    """
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",  # MinIO ignores this, but boto3 requires it
    )


def ensure_bucket_exists():
    """Create the default bucket if it doesn't already exist.

    Called once at server startup (from main.py).  Safe to call multiple
    times — the HEAD check is idempotent.
    """
    s3 = _get_s3_client()
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
        logger.info("MinIO bucket '%s' already exists.", MINIO_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=MINIO_BUCKET)
        logger.info("MinIO bucket '%s' created.", MINIO_BUCKET)


def put_object(key: str, data: bytes) -> int:
    """Upload raw bytes to MinIO under the given key.

    Args:
        key:  The S3 object key (e.g. "1/docs/readme.txt/v2").
        data: The raw bytes to store.

    Returns:
        The number of bytes written.
    """
    s3 = _get_s3_client()
    s3.put_object(
        Bucket=MINIO_BUCKET,
        Key=key,
        Body=data,
        ContentLength=len(data),
    )
    logger.debug("PUT %s (%d bytes)", key, len(data))
    return len(data)


def put_object_stream(key: str, stream, length: int) -> int:
    """Upload a file-like stream to MinIO.

    Args:
        key:    The S3 object key.
        stream: A file-like object with a .read() method.
        length: The exact number of bytes in the stream.

    Returns:
        The number of bytes written.
    """
    s3 = _get_s3_client()
    s3.put_object(
        Bucket=MINIO_BUCKET,
        Key=key,
        Body=stream,
        ContentLength=length,
    )
    logger.debug("PUT (stream) %s (%d bytes)", key, length)
    return length


def get_object(key: str) -> bytes:
    """Download an object from MinIO and return its bytes.

    Raises:
        ClientError: If the key does not exist.
    """
    s3 = _get_s3_client()
    response = s3.get_object(Bucket=MINIO_BUCKET, Key=key)
    data = response["Body"].read()
    logger.debug("GET %s (%d bytes)", key, len(data))
    return data


def delete_object(key: str):
    """Delete an object from MinIO.  No-op if the key doesn't exist."""
    s3 = _get_s3_client()
    s3.delete_object(Bucket=MINIO_BUCKET, Key=key)
    logger.debug("DELETE %s", key)


def assemble_chunks(chunk_keys: list[str], final_key: str) -> int:
    """Download chunk objects, concatenate them, and upload the result.

    This is the server-side assembly step after all chunks for a file
    have been received.  Each chunk key is downloaded, concatenated in
    order, and the result is uploaded to final_key.  The individual
    chunk objects are then deleted.

    Args:
        chunk_keys: Ordered list of S3 keys for the chunks.
        final_key:  The destination S3 key for the assembled file.

    Returns:
        Total assembled size in bytes.
    """
    s3 = _get_s3_client()
    assembled = io.BytesIO()

    for ck in chunk_keys:
        resp = s3.get_object(Bucket=MINIO_BUCKET, Key=ck)
        assembled.write(resp["Body"].read())

    total_bytes = assembled.tell()
    assembled.seek(0)

    s3.put_object(
        Bucket=MINIO_BUCKET,
        Key=final_key,
        Body=assembled,
        ContentLength=total_bytes,
    )

    # Clean up individual chunk objects
    for ck in chunk_keys:
        s3.delete_object(Bucket=MINIO_BUCKET, Key=ck)

    logger.info("Assembled %d chunks → %s (%d bytes)", len(chunk_keys), final_key, total_bytes)
    return total_bytes
