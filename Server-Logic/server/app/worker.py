"""
worker.py — RQ Background Task Definitions (Week 8)

This module defines the heavy-lifting functions that run OUTSIDE the
FastAPI request/response cycle.  They are enqueued by the sync router
and executed by a standalone `rq worker` process.

Architecture:
    FastAPI endpoint  ──enqueue──▶  Redis Queue  ──dequeue──▶  RQ Worker
    (returns 202)                                              (this file)

Each task function receives primitive arguments (ints, strings) rather
than ORM objects, because the worker process has its own DB session
and its own connection to MinIO.

Running the worker:
    cd Server-Logic/server
    rq worker shadowdrive-jobs --with-scheduler

Environment variables (same as the FastAPI server):
    REDIS_URL          = redis://localhost:6379/0
    MINIO_ENDPOINT     = http://localhost:9000
    MINIO_ACCESS_KEY   = admin
    MINIO_SECRET_KEY   = password
    MINIO_BUCKET       = shadowdrive
    DATABASE_URL       = postgresql://user:SDrive516477%23@localhost/shadowdrive
"""

import os
import io
import hashlib
import logging
from datetime import datetime, timezone

from redis import Redis
from rq import Queue
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import storage
from app.models import Version, ChunkUpload, UploadStatus

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ─── Redis Connection ────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)

# The single queue all ShadowDrive jobs are pushed to.
QUEUE_NAME = "shadowdrive-jobs"
task_queue = Queue(QUEUE_NAME, connection=redis_conn)

# ─── Worker-side DB Session ──────────────────────────────────────────────────
# The worker runs in a separate process, so it needs its own engine/session.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:SDrive516477%23@localhost/shadowdrive"
)
_engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
_SessionFactory = sessionmaker(bind=_engine)


def _get_session():
    """Create a short-lived session for a single job execution."""
    return _SessionFactory()


# ─── Background Tasks ────────────────────────────────────────────────────────

def verify_file_hash(version_id: int, expected_hash: str) -> dict:
    """Download the assembled file from MinIO and verify its SHA-256.

    Called after a single-shot upload (POST /sync/upload) or after all
    chunks have been assembled.  If the hash matches, the version is
    marked 'complete'.  If it doesn't, the version is marked 'failed'
    and the corrupt object is left in MinIO for forensic inspection.

    Args:
        version_id:    The versions.id to verify.
        expected_hash: The SHA-256 hex digest the client announced.

    Returns:
        A dict with the job result for RQ's result store.
    """
    db = _get_session()
    try:
        version = db.query(Version).filter(Version.id == version_id).first()
        if not version:
            logger.error("verify_file_hash: version_id=%d not found", version_id)
            return {"status": "error", "reason": "version_not_found"}

        # ── Download from MinIO and compute SHA-256 ──────────────────────
        try:
            file_bytes = storage.get_object(version.storage_path)
        except Exception as e:
            logger.error(
                "verify_file_hash: MinIO read failed for '%s': %s",
                version.storage_path, e
            )
            version.upload_status = UploadStatus.failed
            db.commit()
            return {"status": "failed", "reason": f"minio_read_error: {e}"}

        actual_hash = hashlib.sha256(file_bytes).hexdigest()

        if actual_hash == expected_hash:
            version.upload_status = UploadStatus.complete
            db.commit()
            logger.info(
                "verify_file_hash: version_id=%d PASSED (hash=%s, %d bytes)",
                version_id, actual_hash, len(file_bytes)
            )
            return {
                "status": "complete",
                "version_id": version_id,
                "hash": actual_hash,
                "size_bytes": len(file_bytes),
            }
        else:
            version.upload_status = UploadStatus.failed
            db.commit()
            logger.warning(
                "verify_file_hash: version_id=%d FAILED — "
                "expected %s, got %s",
                version_id, expected_hash, actual_hash
            )
            return {
                "status": "failed",
                "version_id": version_id,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            }

    except Exception as exc:
        # Catch-all: mark the version as failed so it's not stuck in
        # 'processing' forever.
        try:
            version = db.query(Version).filter(Version.id == version_id).first()
            if version:
                version.upload_status = UploadStatus.failed
                db.commit()
        except Exception:
            db.rollback()
        logger.exception("verify_file_hash: unhandled error for version_id=%d", version_id)
        raise exc
    finally:
        db.close()


def assemble_and_verify_chunks(version_id: int, expected_hash: str) -> dict:
    """Assemble chunked uploads and verify the result.

    This combines two operations that were previously done inline inside
    the /upload_chunk endpoint:
        1. Read all chunk objects from MinIO, concatenate them, and
           upload the assembled file under the version's storage_path.
        2. Compute the SHA-256 of the assembled result and compare
           against the client's announced hash.

    On success the version transitions to 'complete'.
    On failure it transitions to 'failed'.

    Args:
        version_id:    The versions.id whose chunks are ready.
        expected_hash: The SHA-256 hex digest the client announced.

    Returns:
        A dict with the job result.
    """
    db = _get_session()
    try:
        version = db.query(Version).filter(Version.id == version_id).first()
        if not version:
            logger.error("assemble_and_verify: version_id=%d not found", version_id)
            return {"status": "error", "reason": "version_not_found"}

        # ── Step 1: Gather chunk keys in order ───────────────────────────
        all_chunks = (
            db.query(ChunkUpload)
            .filter(ChunkUpload.version_id == version_id)
            .order_by(ChunkUpload.chunk_index.asc())
            .all()
        )

        if not all_chunks:
            version.upload_status = UploadStatus.failed
            db.commit()
            return {"status": "failed", "reason": "no_chunks_found"}

        chunk_keys = [c.chunk_storage_key for c in all_chunks]
        final_key = version.storage_path

        # ── Step 2: Assemble in MinIO ────────────────────────────────────
        try:
            total_bytes = storage.assemble_chunks(chunk_keys, final_key)
        except Exception as e:
            logger.error("assemble_and_verify: assembly failed: %s", e)
            version.upload_status = UploadStatus.failed
            db.commit()
            return {"status": "failed", "reason": f"assembly_error: {e}"}

        # Update version with final size
        version.size_bytes = total_bytes

        # ── Step 3: Clean up chunk records ────────────────────────────────
        db.query(ChunkUpload).filter(
            ChunkUpload.version_id == version_id
        ).delete()

        # ── Step 4: Hash verification ────────────────────────────────────
        try:
            file_bytes = storage.get_object(final_key)
        except Exception as e:
            logger.error("assemble_and_verify: re-read failed: %s", e)
            version.upload_status = UploadStatus.failed
            db.commit()
            return {"status": "failed", "reason": f"verify_read_error: {e}"}

        actual_hash = hashlib.sha256(file_bytes).hexdigest()

        if actual_hash == expected_hash:
            version.upload_status = UploadStatus.complete
            db.commit()
            logger.info(
                "assemble_and_verify: version_id=%d PASSED "
                "(%d chunks, %d bytes, hash=%s)",
                version_id, len(all_chunks), total_bytes, actual_hash
            )
            return {
                "status": "complete",
                "version_id": version_id,
                "hash": actual_hash,
                "size_bytes": total_bytes,
                "chunks_assembled": len(all_chunks),
            }
        else:
            version.upload_status = UploadStatus.failed
            db.commit()
            logger.warning(
                "assemble_and_verify: version_id=%d hash MISMATCH — "
                "expected %s, got %s",
                version_id, expected_hash, actual_hash
            )
            return {
                "status": "failed",
                "version_id": version_id,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            }

    except Exception as exc:
        try:
            version = db.query(Version).filter(Version.id == version_id).first()
            if version:
                version.upload_status = UploadStatus.failed
                db.commit()
        except Exception:
            db.rollback()
        logger.exception(
            "assemble_and_verify: unhandled error for version_id=%d",
            version_id
        )
        raise exc
    finally:
        db.close()


# ─── Queue Helpers (imported by the sync router) ─────────────────────────────

def enqueue_verify(version_id: int, expected_hash: str) -> str:
    """Push a verify_file_hash job onto the queue. Returns the RQ job ID."""
    job = task_queue.enqueue(
        verify_file_hash,
        version_id,
        expected_hash,
        job_timeout="10m",
        retry=None,
    )
    logger.info("Enqueued verify_file_hash job=%s for version_id=%d", job.id, version_id)
    return job.id


def enqueue_assemble_and_verify(version_id: int, expected_hash: str) -> str:
    """Push an assemble_and_verify_chunks job onto the queue. Returns the RQ job ID."""
    job = task_queue.enqueue(
        assemble_and_verify_chunks,
        version_id,
        expected_hash,
        job_timeout="30m",
        retry=None,
    )
    logger.info(
        "Enqueued assemble_and_verify job=%s for version_id=%d",
        job.id, version_id
    )
    return job.id
