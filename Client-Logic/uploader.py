"""
uploader.py — Outbound Upload Pipeline

Manages the upload queue, parallel chunk uploads with on-the-fly encryption,
hash caching, and exponential-backoff retry logic.
Extracted from sync_engine.py for maintainability.
"""

import hashlib
import os
import queue
import random
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import config
import crypto_utils
import hash_utils
import network_client
from loguru import logger
from state import PathLock, _stop_event

from database import get_connection

# Dedicated executor for parallel chunk uploads
_upload_chunk_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="upload-chunk")


@dataclass
class UploadJob:
    local_path: str
    remote_path: str
    file_hash: str
    version_id: int
    file_size: int
    event_id: int
    plaintext_hash: str = None
    retry_count: int = 0
    completed_chunks: set = None
    missing_chunks: list = None
    file_id: int = 0
    nonces: list = None
    aborted: threading.Event = field(default_factory=threading.Event, init=False)


upload_queue: queue.Queue = queue.Queue()

# Thread-safe in-flight tracking set to prevent queue bloat
_in_flight_events = set()
_in_flight_lock = threading.Lock()

_active_jobs = {}
_active_jobs_lock = threading.Lock()


def mark_in_flight(event_id: int, job: Optional[UploadJob] = None) -> bool:
    """Returns True if the event was successfully marked as in-flight (not already tracked)."""
    with _in_flight_lock:
        if event_id in _in_flight_events:
            return False
        _in_flight_events.add(event_id)
        if job is not None:
            with _active_jobs_lock:
                _active_jobs[event_id] = job
        return True


def clear_in_flight(event_id: int):
    """Remove an event from the in-flight set."""
    with _in_flight_lock:
        _in_flight_events.discard(event_id)
        with _active_jobs_lock:
            _active_jobs.pop(event_id, None)


def is_in_flight(event_id: int) -> bool:
    """Check if an event is currently in-flight."""
    with _in_flight_lock:
        return event_id in _in_flight_events


def get_active_transfers_progress() -> dict[int, dict]:
    """Helper to return dynamic upload progress details for active/queued jobs."""
    results = {}
    with _active_jobs_lock:
        for event_id, job in list(_active_jobs.items()):
            total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE if job.file_size > 0 else 1
            completed = len(job.completed_chunks) if job.completed_chunks is not None else 0
            if total_chunks > 1:
                progress = int((completed / total_chunks) * 100)
            else:
                progress = 50 if event_id in _in_flight_events else 0
            
            results[event_id] = {
                "progress": progress,
                "completed_chunks": completed,
                "total_chunks": total_chunks,
            }
    return results


# In-memory cache for prepared encrypted hashes to avoid duplicate passes
_enc_hash_cache = {}
_enc_hash_cache_lock = threading.Lock()



# ─── Encrypted Hash Cache ─────────────────────────────────────────────────────

def get_prepared_encrypted_hashes(full_path: str, plaintext_hash: str) -> tuple[str, list[str]]:
    """Get prepared encrypted hashes from cache or compute them."""
    with _enc_hash_cache_lock:
        if plaintext_hash in _enc_hash_cache:
            return _enc_hash_cache[plaintext_hash]

    enc_file_hash, enc_chunk_hashes = prepare_encrypted_hashes(full_path, plaintext_hash)

    with _enc_hash_cache_lock:
        if len(_enc_hash_cache) > 200:
            _enc_hash_cache.pop(next(iter(_enc_hash_cache)))
        _enc_hash_cache[plaintext_hash] = (enc_file_hash, enc_chunk_hashes)

    return enc_file_hash, enc_chunk_hashes


# ─── Zero-Knowledge Encryption Helpers ───────────────────────────────────────

def get_or_create_nonces(file_path: str, plaintext_hash: str, total_chunks: int, conn=None) -> list[bytes]:
    """Look up or generate 12-byte nonces for each chunk of a file.
    Persisted in pending_chunk_uploads for deterministic retry behavior."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    cur = conn.cursor()

    cur.execute("DELETE FROM pending_chunk_uploads WHERE file_path = ? AND plaintext_hash != ?",
                (file_path, plaintext_hash))
    conn.commit()

    nonces = []
    for i in range(total_chunks):
        cur.execute("SELECT nonce FROM pending_chunk_uploads WHERE file_path = ? AND chunk_index = ?",
                    (file_path, i))
        row = cur.fetchone()
        if row:
            nonces.append(row[0])
        else:
            nonce = os.urandom(12)
            cur.execute("""
                INSERT OR REPLACE INTO pending_chunk_uploads (file_path, chunk_index, nonce, plaintext_hash)
                VALUES (?, ?, ?, ?)
            """, (file_path, i, nonce, plaintext_hash))
            nonces.append(nonce)

    conn.commit()
    if should_close:
        conn.close()
    return nonces


def prepare_encrypted_hashes(full_path: str, plaintext_hash: str, conn=None) -> tuple[str, list[str]]:
    """Calculate encrypted hashes of the file and its chunks without storing full encrypted bytes in memory."""
    file_size = os.path.getsize(full_path)
    if file_size == 0:
        total_chunks = 1
        chunk_sizes = [0]
    elif file_size < config.CHUNK_THRESHOLD:
        total_chunks = 1
        chunk_sizes = [file_size]
    else:
        total_chunks = (file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE
        chunk_sizes = []
        for i in range(total_chunks):
            offset = i * config.CHUNK_SIZE
            chunk_sizes.append(min(config.CHUNK_SIZE, file_size - offset))

    nonces = get_or_create_nonces(full_path, plaintext_hash, total_chunks, conn=conn)

    file_sha = hashlib.sha256()
    encrypted_chunk_hashes = []

    with open(full_path, "rb") as f:
        for i in range(total_chunks):
            chunk_plain = f.read(chunk_sizes[i])
            if config.COMPRESSION == "zlib":
                chunk_plain = crypto_utils.compress_before_encrypt(chunk_plain)
            nonce = nonces[i]
            nonce_out, tag, ciphertext = crypto_utils.encrypt_chunk(config.encryption_key, chunk_plain, nonce)
            packed = crypto_utils.pack_encrypted(nonce_out, tag, ciphertext)

            file_sha.update(packed)
            chunk_hash = hashlib.sha256(packed).hexdigest()
            encrypted_chunk_hashes.append(chunk_hash)

    return file_sha.hexdigest(), encrypted_chunk_hashes


def get_single_encrypted_chunk(full_path: str, plaintext_hash: str, chunk_index: int, total_chunks: int, nonce: Optional[bytes] = None) -> bytes:
    """Encrypt and return a single chunk on the fly."""
    if nonce is None:
        nonces = get_or_create_nonces(full_path, plaintext_hash, total_chunks)
        nonce = nonces[chunk_index]

    file_size = os.path.getsize(full_path)
    offset = chunk_index * config.CHUNK_SIZE
    chunk_size = min(config.CHUNK_SIZE, file_size - offset)

    with open(full_path, "rb") as f:
        f.seek(offset)
        chunk_plain = f.read(chunk_size)

    nonce_out, tag, ciphertext = crypto_utils.encrypt_chunk(config.encryption_key, chunk_plain, nonce)
    return crypto_utils.pack_encrypted(nonce_out, tag, ciphertext)


def ack_upload(file_id: int, version_id: int):
    """Tell the server that THIS device now has this version."""
    try:
        from heartbeat import get_device_id
        network_client.ack_sync(
            device_id=get_device_id(),
            file_id=file_id,
            version_id=version_id,
        )
    except Exception as e:
        logger.warning("ack_sync failed for file_id={}: {}", file_id, e)


def finalize_local_db_after_upload(full_path: str, plaintext_hash: str, version_id: int):
    """Finalize local shadow.db tracking after successful upload."""
    conn = get_connection()
    cur = conn.cursor()

    if config.encryption_key:
        enc_file_hash, enc_chunk_hashes = get_prepared_encrypted_hashes(full_path, plaintext_hash)
        cur.execute("""
            UPDATE files
            SET version_id = ?, encrypted_hash = ?
            WHERE file_path = ? AND hash = ?
        """, (version_id, enc_file_hash, full_path, plaintext_hash))

        cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (full_path,))
        for idx, ch in enumerate(enc_chunk_hashes):
            cur.execute("""
                INSERT INTO chunk_signatures (file_path, chunk_index, hash)
                VALUES (?, ?, ?)
            """, (full_path, idx, ch))
    else:
        cur.execute("""
            UPDATE files
            SET version_id = ?
            WHERE file_path = ? AND hash = ?
        """, (version_id, full_path, plaintext_hash))

    conn.commit()
    conn.close()


# ─── Upload Worker ────────────────────────────────────────────────────────────

def upload_worker():
    """Worker thread consuming upload jobs from the queue."""
    logger.info("Upload worker initialized and watching for jobs.")
    while not _stop_event.is_set():
        try:
            job = upload_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            with PathLock(job.local_path):
                if not os.path.exists(job.local_path):
                    logger.warning("File vanished before transit: {}", job.local_path)
                    mark_synced_db(job.event_id)
                    clear_in_flight(job.event_id)
                    continue

                expected_plain_hash = job.plaintext_hash if job.plaintext_hash else job.file_hash
                current_hash = hash_utils.hash_file(job.local_path)
                if current_hash != expected_plain_hash:
                    logger.info("Job for {} is obsolete (hash changed). Discarding.", job.remote_path)
                    mark_synced_db(job.event_id)
                    clear_in_flight(job.event_id)
                    continue

                if job.completed_chunks is None:
                    job.completed_chunks = set()

                total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE
                if config.encryption_key and job.nonces is None:
                    job.nonces = get_or_create_nonces(job.local_path, expected_plain_hash, total_chunks)

                if job.file_size < config.CHUNK_THRESHOLD:
                    if config.encryption_key:
                        nonce_val = job.nonces[0] if job.nonces else None
                        enc_data = get_single_encrypted_chunk(job.local_path, expected_plain_hash, 0, 1, nonce=nonce_val)
                        success, data = network_client.upload_file(
                            job.remote_path, job.local_path, data=enc_data, version_id=job.version_id
                        )
                    else:
                        success, data = network_client.upload_file(
                            job.remote_path, job.local_path, version_id=job.version_id
                        )
                    if success:
                        logger.success("Uploaded {} (single-shot)", job.remote_path)
                        version_id = data.get("version_id", 0)
                        finalize_local_db_after_upload(job.local_path, expected_plain_hash, version_id)
                        ack_upload(job.file_id, version_id)
                        mark_synced_db(job.event_id)
                        clear_in_flight(job.event_id)
                    else:
                        handle_failed_job(job, data)
                else:
                    _upload_chunks_resilient(job, expected_plain_hash)

        except Exception as e:
            logger.error("Unexpected crash in upload worker: {}", e)
            handle_failed_job(job, {"error": str(e), "retriable": True})
        finally:
            upload_queue.task_done()


def _upload_chunk_worker(job: UploadJob, chunk_index: int, total_chunks: int,
                          expected_plain_hash: str, file_hash_to_send: str,
                          completed_lock: threading.Lock, nonce: Optional[bytes] = None):
    """Worker task to encrypt/read and upload a single chunk."""
    if job.aborted.is_set():
        return

    if config.encryption_key:
        chunk_data = get_single_encrypted_chunk(job.local_path, expected_plain_hash, chunk_index, total_chunks, nonce=nonce)
    else:
        offset = chunk_index * config.CHUNK_SIZE
        chunk_size = min(config.CHUNK_SIZE, job.file_size - offset)
        with open(job.local_path, 'rb') as f:
            f.seek(offset)
            chunk_data = f.read(chunk_size)

    if job.aborted.is_set():
        return

    resp = network_client._request(
        "POST",
        "/sync/upload_chunk",
        files={"chunk": (f"chunk_{chunk_index}", chunk_data)},
        data={
            "version_id": str(job.version_id),
            "chunk_index": str(chunk_index),
            "total_chunks": str(total_chunks),
            "file_hash": file_hash_to_send,
        }
    )
    resp.raise_for_status()
    with completed_lock:
        job.completed_chunks.add(chunk_index)


def _upload_chunks_resilient(job: UploadJob, expected_plain_hash: str):
    """Upload file chunks concurrently with per-chunk retry and resume capability."""
    total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE

    if job.missing_chunks is not None:
        chunks_to_upload = set(job.missing_chunks)
        skipped = total_chunks - len(chunks_to_upload)
        if skipped > 0:
            logger.info("Skipping {}/{} unchanged chunks for {}", skipped, total_chunks, job.remote_path)
    else:
        chunks_to_upload = set(range(total_chunks))

    logger.info("Spooling {}/{} chunks for {} (already finished: {})",
                len(chunks_to_upload), total_chunks, job.remote_path, len(job.completed_chunks))

    file_hash_to_send = job.file_hash
    completed_lock = threading.Lock()

    futures = []
    for chunk_index in range(total_chunks):
        if chunk_index not in chunks_to_upload:
            continue
        if chunk_index in job.completed_chunks:
            continue

        nonce_val = job.nonces[chunk_index] if job.nonces else None
        futures.append(_upload_chunk_executor.submit(
            _upload_chunk_worker, job, chunk_index, total_chunks,
            expected_plain_hash, file_hash_to_send, completed_lock, nonce_val
        ))

    try:
        for future in as_completed(futures):
            if job.aborted.is_set():
                break
            try:
                future.result()
            except Exception:
                job.aborted.set()
                raise
    except Exception as e:
        logger.error("Failure during concurrent uploads: {}", e)
        handle_failed_job(job, {"error": str(e)})
        return

    if job.aborted.is_set():
        handle_failed_job(job, {"error": "Upload aborted due to sub-task failure"})
        return

    logger.success("Completed all blocks for {}", job.remote_path)
    finalize_local_db_after_upload(job.local_path, expected_plain_hash, job.version_id)
    ack_upload(job.file_id, job.version_id)
    mark_synced_db(job.event_id)
    clear_in_flight(job.event_id)


# ─── Retry Logic ──────────────────────────────────────────────────────────────

def handle_failed_job(job: UploadJob, error_data: dict):
    """Exponential backoff retry for failed uploads."""
    retriable = error_data.get("retriable", True)
    error_msg = error_data.get("error", "Unknown error")

    if not retriable:
        logger.error("Non-retriable error for {}: {}. Discarding.", job.remote_path, error_msg)
        mark_synced_db(job.event_id)
        clear_in_flight(job.event_id)
        return

    if job.retry_count < config.UPLOAD_MAX_RETRIES:
        job.retry_count += 1
        max_backoff = getattr(config, "RETRY_MAX_BACKOFF_SECONDS", 60)
        backoff = min(max_backoff, config.RETRY_BACKOFF_SECONDS * (2 ** (job.retry_count - 1)))
        jitter = random.uniform(0.1, 1.0)
        total = backoff + jitter

        logger.warning("Retry #{} for {} in {:.1f}s: {}", job.retry_count, job.remote_path, total, error_msg)

        def _re_enqueue():
            upload_queue.put(job)

        t = threading.Timer(total, _re_enqueue)
        t.daemon = True
        t.start()
    else:
        logger.error("Max retries hit for {}. Will retry next sync cycle.", job.remote_path)
        clear_in_flight(job.event_id)


def mark_synced_db(event_id: int):
    """Mark an event as synced in the local database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE events SET is_synced = 1 WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error("Mark synced exception: {}", e)
