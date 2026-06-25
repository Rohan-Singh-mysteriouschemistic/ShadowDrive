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
import json
import hashlib
import sys
from datetime import datetime, timezone

from loguru import logger
from redis import Redis
from rq import Queue
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import storage
from app.models import Version, ChunkUpload, UploadStatus

logger.remove()
logger.add(sys.stderr, level="INFO")

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


def _notify_completion(version: Version, status_str: str):
    """Publish a completion event to Redis for the SSE bridge.
    
    Args:
        version:    The Version ORM object (must be attached to an active session).
        status_str: 'complete' or 'failed'.
    """
    notification = {
        "user_id": version.file.user_id,
        "type": f"upload_{status_str}",
        "data": {
            "file_id": version.file_id,
            "file_path": version.file.file_path,
            "version_id": version.id,
            "status": status_str,
        }
    }
    redis_conn.publish("shadowdrive:events", json.dumps(notification))
    logger.info(
        "Published {} event to Redis for file='{}' (user_id={})",
        notification["type"], version.file.file_path, version.file.user_id
    )


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
            logger.error("verify_file_hash: version_id={} not found", version_id)
            return {"status": "error", "reason": "version_not_found"}

        # ── Download from MinIO and compute SHA-256 ──────────────────────
        try:
            file_bytes = storage.get_object(version.storage_path)
        except Exception as e:
            logger.error(
                "verify_file_hash: MinIO read failed for '{}': {}",
                version.storage_path, e
            )
            version.upload_status = UploadStatus.failed
            db.commit()
            _notify_completion(version, "failed")
            return {"status": "failed", "reason": f"minio_read_error: {e}"}

        actual_hash = hashlib.sha256(file_bytes).hexdigest()

        if actual_hash == expected_hash:
            version.upload_status = UploadStatus.complete
            db.commit()
            _notify_completion(version, "complete")
            logger.info(
                "verify_file_hash: version_id={} PASSED (hash={}, {} bytes)",
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
            _notify_completion(version, "failed")
            logger.warning(
                "verify_file_hash: version_id={} FAILED — "
                "expected {}, got {}",
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
                _notify_completion(version, "failed")
        except Exception:
            db.rollback()
        logger.exception("verify_file_hash: unhandled error for version_id={}", version_id)
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
            logger.error("assemble_and_verify: version_id={} not found", version_id)
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
            _notify_completion(version, "failed")
            return {"status": "failed", "reason": "no_chunks_found"}

        chunk_keys = [c.chunk_storage_key for c in all_chunks]
        final_key = version.storage_path

        # ── Step 2: Assemble in MinIO ────────────────────────────────────
        try:
            total_bytes = storage.assemble_chunks(chunk_keys, final_key)
        except Exception as e:
            logger.error("assemble_and_verify: assembly failed: {}", e)
            version.upload_status = UploadStatus.failed
            db.commit()
            _notify_completion(version, "failed")
            return {"status": "failed", "reason": f"assembly_error: {e}"}

        # Update version with final size
        version.size_bytes = total_bytes

        # ── Step 3: Clean up chunk records ────────────────────────────────
        db.query(ChunkUpload).filter(
            ChunkUpload.version_id == version_id
        ).delete()

        # ── Step 4: Hash verification ────────────────────────────────────
        try:
            sha256 = hashlib.sha256()
            body_stream = storage.get_object_stream(final_key)
            while True:
                data = body_stream.read(1024 * 1024)
                if not data:
                    break
                sha256.update(data)
            actual_hash = sha256.hexdigest()
        except Exception as e:
            logger.error("assemble_and_verify: re-read/hash failed: {}", e)
            version.upload_status = UploadStatus.failed
            db.commit()
            _notify_completion(version, "failed")
            return {"status": "failed", "reason": f"verify_read_error: {e}"}

        if actual_hash == expected_hash:
            version.upload_status = UploadStatus.complete
            db.commit()
            _notify_completion(version, "complete")
            logger.info(
                "assemble_and_verify: version_id={} PASSED "
                "({} chunks, {} bytes, hash={})",
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
            _notify_completion(version, "failed")
            logger.warning(
                "assemble_and_verify: version_id={} hash MISMATCH — "
                "expected {}, got {}",
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
                _notify_completion(version, "failed")
        except Exception:
            db.rollback()
        logger.exception(
            "assemble_and_verify: unhandled error for version_id={}",
            version_id
        )
        raise exc
    finally:
        db.close()


# ─── Queue Helpers (imported by the sync router) ─────────────────────────────

def enqueue_verify(version_id: int, expected_hash: str) -> str:
    """Push a verify_file_hash job onto the queue. Returns the RQ job ID."""
    # Create a fresh Redis connection per enqueue to avoid stale connection issues
    # (module-level connections can time out between uploads in long-running sessions)
    conn = Redis.from_url(REDIS_URL)
    q = Queue(QUEUE_NAME, connection=conn)
    job = q.enqueue(
        verify_file_hash,
        version_id,
        expected_hash,
        job_timeout="10m",
        retry=None,
    )
    logger.info("Enqueued verify_file_hash job={} for version_id={}", job.id, version_id)
    return job.id


def enqueue_assemble_and_verify(version_id: int, expected_hash: str) -> str:
    """Push an assemble_and_verify_chunks job onto the queue. Returns the RQ job ID."""
    # Create a fresh Redis connection per enqueue to avoid stale connection issues
    conn = Redis.from_url(REDIS_URL)
    q = Queue(QUEUE_NAME, connection=conn)
    job = q.enqueue(
        assemble_and_verify_chunks,
        version_id,
        expected_hash,
        job_timeout="30m",
        retry=None,
    )
    logger.info(
        "Enqueued assemble_and_verify job={} for version_id={}",
        job.id, version_id
    )
    return job.id
