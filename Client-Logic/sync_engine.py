"""
sync_engine.py — Dual-direction Synchronization Core Engine (Week 6/7 + Phase 1 Delta Sync)
Manages outbound event queues and executes metadata diff reconstruction.
"""

import time
import sqlite3
import os
import threading
import queue
import hashlib
import logging
from typing import Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

import network_client
import config
import hash_utils  # <--- WEEK 7 ADDITION: Needed for conflict state checking
import crypto_utils
import event_listener
from diff_engine import get_db_connection

# Dedicated worker pools for different pipelines to prevent deadlock and HOL blocking
_upload_chunk_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="upload-chunk")
_download_chunk_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="download-chunk")
_download_job_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="download-job")

# In-memory cache for prepared encrypted hashes to avoid duplicate passes
_enc_hash_cache = {}
_enc_hash_cache_lock = threading.Lock()

# Graceful shutdown event
_stop_event = threading.Event()

# Path-level locks dictionary to serialize uploads/downloads of the same file path
_path_locks = {}
_path_locks_lock = threading.Lock()

class PathLock:
    """Thread-safe context manager to serialize operations on a specific file path."""
    def __init__(self, path: str):
        self.path = os.path.normpath(path)
        with _path_locks_lock:
            if self.path not in _path_locks:
                _path_locks[self.path] = threading.Lock()
            self.lock = _path_locks[self.path]

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.lock.release()
        except RuntimeError:
            pass


def get_prepared_encrypted_hashes(full_path: str, plaintext_hash: str) -> tuple[str, list[str]]:
    """Get prepared encrypted hashes from cache or compute them."""
    with _enc_hash_cache_lock:
        if plaintext_hash in _enc_hash_cache:
            return _enc_hash_cache[plaintext_hash]
            
    enc_file_hash, enc_chunk_hashes = prepare_encrypted_hashes(full_path, plaintext_hash)
    
    with _enc_hash_cache_lock:
        if len(_enc_hash_cache) > 200:
            # Simple FIFO eviction
            _enc_hash_cache.pop(next(iter(_enc_hash_cache)))
        _enc_hash_cache[plaintext_hash] = (enc_file_hash, enc_chunk_hashes)
        
    return enc_file_hash, enc_chunk_hashes


@dataclass
class UploadJob:
    local_path: str
    remote_path: str
    file_hash: str        # Encrypted hash if encryption is active, else plaintext hash
    version_id: int
    file_size: int
    event_id: int        
    plaintext_hash: str = None  # Plaintext hash to check for local changes/obsolescence
    retry_count: int = 0
    completed_chunks: set = None
    missing_chunks: list = None  # Phase 1: Only these chunk indices need uploading
    file_id: int = 0
    nonces: list = None
    aborted: threading.Event = field(default_factory=threading.Event, init=False)

upload_queue: queue.Queue = queue.Queue()

# Thread-safe in-flight tracking set to prevent queue bloat
_in_flight_events = set()
_in_flight_lock = threading.Lock()

# Thread-local storage for preventing watcher feedback loops
_local_mutator = threading.local()
_local_mutator.active = False

def _mark_in_flight(event_id: int) -> bool:
    with _in_flight_lock:
        if event_id in _in_flight_events:
            return False
        _in_flight_events.add(event_id)
        return True

def _clear_in_flight(event_id: int):
    with _in_flight_lock:
        _in_flight_events.discard(event_id)

# ─── Zero-Knowledge Encryption Helpers ───────────────────────────────────────

def get_or_create_nonces(file_path: str, plaintext_hash: str, total_chunks: int, conn=None) -> list[bytes]:
    """
    Look up or generate the 12-byte nonces for each chunk of a file.
    To ensure deterministic behavior on retries, we persist these nonces in the 
    `pending_chunk_uploads` table along with the plaintext_hash.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True
    cur = conn.cursor()
    
    # Clean up obsolete nonces for this path
    cur.execute("DELETE FROM pending_chunk_uploads WHERE file_path = ? AND plaintext_hash != ?", (file_path, plaintext_hash))
    conn.commit()
    
    nonces = []
    for i in range(total_chunks):
        cur.execute("SELECT nonce FROM pending_chunk_uploads WHERE file_path = ? AND chunk_index = ?", (file_path, i))
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
    """
    Calculate the encrypted hashes of the file and its chunks without storing the full encrypted bytes in memory.
    """
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


def _ack_upload(file_id: int, version_id: int):
    """Tell the server that THIS device now has this version."""
    try:
        network_client.ack_sync(
            device_id=_get_device_id(),
            file_id=file_id,
            version_id=version_id,
        )
    except Exception as e:
        print(f"ack_sync failed for file_id={file_id}: {e}")


def finalize_local_db_after_upload(full_path: str, plaintext_hash: str, version_id: int):
    """
    Once an upload succeeds and the server registers the version, finalize
    local shadow.db tracking tables: version_id, encrypted_hash, and chunk_signatures.
    """
    conn = get_db_connection()
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


def is_local_mutation_active() -> bool:
    return getattr(_local_mutator, "active", False)


def _upload_worker():
    """Worker thread eating outbound tasks out of the pipeline queue."""
    print("[UPLOAD WORKER] Initialized and watching for jobs.")
    while not _stop_event.is_set():
        try:
            job = upload_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            with PathLock(job.local_path):
                # 1. Verification Phase: Check if file still exists
                if not os.path.exists(job.local_path):
                    print(f"[UPLOAD WORKER] File vanished before transit: {job.local_path}")
                    _mark_synced_db(job.event_id)
                    _clear_in_flight(job.event_id)
                    continue
                    
                # 2. Obsolete Check Phase: If hash has changed locally, discard this job
                expected_plain_hash = job.plaintext_hash if job.plaintext_hash else job.file_hash
                current_hash = hash_utils.hash_file(job.local_path)
                if current_hash != expected_plain_hash:
                    print(f"[UPLOAD WORKER] Job for {job.remote_path} is obsolete (local hash changed from {expected_plain_hash[:8]} to {current_hash[:8] if current_hash else 'None'}). Discarding.")
                    _mark_synced_db(job.event_id)
                    _clear_in_flight(job.event_id)
                    continue

                # Initialize chunk completion tracking for this job if not set
                if job.completed_chunks is None:
                    job.completed_chunks = set()

                total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE
                if config.encryption_key and job.nonces is None:
                    job.nonces = get_or_create_nonces(job.local_path, expected_plain_hash, total_chunks)

                if job.file_size < config.CHUNK_THRESHOLD:
                    if config.encryption_key:
                        nonce_val = job.nonces[0] if job.nonces else None
                        enc_data = get_single_encrypted_chunk(job.local_path, expected_plain_hash, 0, 1, nonce=nonce_val)
                        success, data = network_client.upload_file(job.remote_path, job.local_path, data=enc_data)
                    else:
                        success, data = network_client.upload_file(job.remote_path, job.local_path)
                    if success:
                        print(f"[UPLOAD SUCCESS] {job.remote_path} (single-shot)")
                        version_id = data.get("version_id", 0)
                        finalize_local_db_after_upload(job.local_path, expected_plain_hash, version_id)
                        _ack_upload(job.file_id, version_id)
                        _mark_synced_db(job.event_id)
                        _clear_in_flight(job.event_id)
                    else:
                        _handle_failed_job(job, data)
                else:
                    _upload_chunks_resilient(job, expected_plain_hash)
                    
        except Exception as e:
            print(f"[UPLOAD ERROR] Unexpected crash in transiting worker: {e}")
            _handle_failed_job(job, {"error": str(e), "retriable": True})
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
    
    # Check if we have server delta info
    if job.missing_chunks is not None:
        chunks_to_upload = set(job.missing_chunks)
        skipped = total_chunks - len(chunks_to_upload)
        if skipped > 0:
            print(f"[DELTA SYNC] Skipping {skipped}/{total_chunks} unchanged chunks for {job.remote_path}")
    else:
        chunks_to_upload = set(range(total_chunks))
    
    print(f"[UPLOAD CHUNKED] Spooling {len(chunks_to_upload)}/{total_chunks} parts for {job.remote_path} (already finished: {len(job.completed_chunks)})")
    
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
            except Exception as e:
                job.aborted.set()
                raise
    except Exception as e:
        print(f"[UPLOAD CHUNKED] Failure during concurrent uploads: {e}")
        _handle_failed_job(job, {"error": str(e)})
        return
                
    if job.aborted.is_set():
        _handle_failed_job(job, {"error": "Upload aborted due to sub-task failure"})
        return

    print(f"[UPLOAD CHUNKED SUCCESS] Completed all blocks for {job.remote_path}")
    finalize_local_db_after_upload(job.local_path, expected_plain_hash, job.version_id)
    _ack_upload(job.file_id, job.version_id)
    _mark_synced_db(job.event_id)
    _clear_in_flight(job.event_id)


def _handle_failed_job(job: UploadJob, error_data: dict):
    """Processes backoff retry increments on critical connection dropped states."""
    import random
    retriable = error_data.get("retriable", True)
    error_msg = error_data.get("error", "Unknown transport error")

    if not retriable:
        print(f"[FATAL FAILURE] Non-retriable error for {job.remote_path}: {error_msg}. Discarding job.")
        _mark_synced_db(job.event_id)
        _clear_in_flight(job.event_id)
        return

    if job.retry_count < config.UPLOAD_MAX_RETRIES:
        job.retry_count += 1
        
        # Calculate exponential backoff capped at config.RETRY_MAX_BACKOFF_SECONDS
        base_backoff = config.RETRY_BACKOFF_SECONDS
        max_backoff = getattr(config, "RETRY_MAX_BACKOFF_SECONDS", 60)
        
        backoff = min(max_backoff, base_backoff * (2 ** (job.retry_count - 1)))
        jitter = random.uniform(0.1, 1.0)
        total_backoff = backoff + jitter
        
        print(f"[RETRY QUEUE] Queued retry #{job.retry_count} for {job.remote_path} in {total_backoff:.2f}s due to: {error_msg}")
        
        def _re_enqueue():
            upload_queue.put(job)
            
        t = threading.Timer(total_backoff, _re_enqueue)
        t.daemon = True
        t.start()
    else:
        print(f"[FATAL FAILURE] Maximum fallback constraints hit for {job.remote_path}. Releasing in-flight hold to retry in next sync cycle.")
        _clear_in_flight(job.event_id)


def _mark_synced_db(event_id: int):
    """Flags internal staging entries completed inside tracking table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE events SET is_synced = 1 WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"[DB ERROR] Mark synced exception: {e}")

# ─── WEEK 6/7 DOWNLOAD PIPELINE logic + Phase 1 Delta Download ──────────────

def _get_device_id() -> Optional[int]:
    """Gets device_id from settings table."""
    dev_id = network_client._get_setting("device_id")
    return int(dev_id) if dev_id else None


def _download_file_worker(remote: dict, device_id: int):
    """Processes a single file download including conflict resolution, download, and DB updates."""
    rel_path = remote["file_path"]
    remote_hash = remote["hash"]
    version_id = remote["version_id"]
    file_id = remote["file_id"]
    storage_path = remote["storage_path"]
    remote_chunk_hashes = remote.get("chunk_hashes", [])

    full_local_path = os.path.normpath(os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep)))

    with PathLock(full_local_path):
        # Use a localized DB connection for the thread
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT hash, encrypted_hash, version_id FROM files WHERE file_path = ?", (full_local_path,))
            row = cur.fetchone()
        except sqlite3.OperationalError:
            cur.execute("SELECT hash FROM files WHERE file_path = ?", (full_local_path,))
            row = cur.fetchone()
            if row:
                row = (row[0], None, 0)

        # WEEK 7: SIMULTANEOUS EDIT CONFLICT DETECTION
        is_conflict = False
        db_plain_hash = None
        db_enc_hash = None
        db_version_id = 0
        if row is not None:
            db_plain_hash = row[0]
            db_enc_hash = row[1]
            db_version_id = row[2] if len(row) > 2 else 0
            
            # FAST PATH: Skip download if we already have this version or a newer one locally!
            if db_version_id >= version_id:
                print(f"[DOWNLOAD PIPELINE] Skipping {rel_path} (local version {db_version_id} >= remote {version_id})")
                network_client.ack_sync(device_id, file_id, db_version_id)
                conn.close()
                return
            
            # Check for updates: compare remote (encrypted) hash to stored encrypted hash
            target_db_hash = db_enc_hash if (db_enc_hash and config.encryption_key) else db_plain_hash
            if target_db_hash != remote_hash:
                # The server has a new version. Check if we ALSO modified our local file!
                cur.execute("SELECT 1 FROM events WHERE file_path = ? AND is_synced = 0", (full_local_path,))
                if cur.fetchone():
                    is_conflict = True

        target_db_hash = db_enc_hash if (db_enc_hash and config.encryption_key) else db_plain_hash
        if row is None or target_db_hash != remote_hash:
            
            # Handle the Conflict Phase Before Downloading
            if is_conflict:
                timestamp = int(time.time())
                root, ext = os.path.splitext(full_local_path)
                conflict_path = f"{root} (Conflicted copy){ext}"
                print(f"[CONFLICT DETECTED] Simultaneous edits on {rel_path}")
                print(f" -> Moving your local work to: {os.path.basename(conflict_path)}")
                import shutil
                shutil.copy2(full_local_path, conflict_path)
            else:
                print(f"[DOWNLOAD PIPELINE] Inconsistency detected. Pulling: {rel_path}")

            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)

            from watcher import suppress_path
            suppress_path(full_local_path)  # ← Suppress BEFORE write

            # ─── Phase 1: Delta Download Reconstruction ──────────────────
            if remote_chunk_hashes:
                _delta_download_file(
                    cur, conn, full_local_path, rel_path,
                    remote_hash, remote_chunk_hashes,
                    version_id, file_id, device_id
                )
            else:
                # Fallback to full single-shot download
                dl_ok, file_bytes = network_client.download_file(storage_path)
                if dl_ok:
                    # Decrypt if Zero-Knowledge Encryption is active
                    if config.encryption_key:
                        try:
                            nonce_in, tag, ciphertext = crypto_utils.unpack_encrypted(file_bytes)
                            file_bytes = crypto_utils.decrypt_chunk(config.encryption_key, nonce_in, tag, ciphertext)
                        except Exception as e:
                            print(f"[CRYPTO ERROR] Failed to decrypt single-shot download for {rel_path}: {e}")
                            conn.close()
                            return

                    with open(full_local_path, "wb") as f:
                        f.write(file_bytes)
                    
                    stat = os.stat(full_local_path)
                    local_plain_hash = hash_utils.hash_file(full_local_path)
                    
                    cur.execute("""
                        INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id, encrypted_hash)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (full_local_path, local_plain_hash, stat.st_size, stat.st_mtime, version_id, remote_hash))
                    conn.commit()
                    print(f"[DOWNLOAD SUCCESS] Materialized update onto filesystem: {rel_path}")
                    
                    # Update server tracking mapping
                    network_client.ack_sync(device_id, file_id, version_id)

        conn.close()


def process_downstream_downloads(device_id: int):
    """
    Fetches the server manifest map, calculates a diff against local metadata tables,
    and updates the local workspace folder.
    """
    success, diff_payload = network_client.get_metadata_diff(device_id=device_id)
    if not success:
        return

    # Phase 1/2: Delete phase run first
    conn = get_db_connection()
    cur = conn.cursor()

    _local_mutator.active = True  # Mute local event logging from handling this disk action
    try:
        deleted_files = diff_payload.get("deleted_files", [])
        for rel_path in deleted_files:
            full_local_path = os.path.normpath(os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep)))
            
            with PathLock(full_local_path):
                try:
                    cur.execute("SELECT hash, version_id FROM files WHERE file_path = ?", (full_local_path,))
                except sqlite3.OperationalError:
                    # Fallback if DB not fully migrated
                    cur.execute("SELECT hash FROM files WHERE file_path = ?", (full_local_path,))
                row = cur.fetchone()
                
                if row:
                    db_hash = row[0]
                    current_local_hash = hash_utils.hash_file(full_local_path)
                    
                    # If the file was changed locally AFTER the last sync, but deleted on the server -> CONFLICT!
                    if current_local_hash and current_local_hash != db_hash:
                        timestamp = int(time.time())
                        root, ext = os.path.splitext(full_local_path)
                        conflict_path = f"{root}_conflict_{timestamp}{ext}"
                        print(f"[CONFLICT] Server deleted '{rel_path}', but you modified it locally!")
                        print(f" -> Preserving your local modifications as: {os.path.basename(conflict_path)}")
                        os.rename(full_local_path, conflict_path)
                    else:
                        print(f"[DOWNLOAD PIPELINE] Server deleted file, removing locally: {rel_path}")
                        if os.path.exists(full_local_path):
                            from watcher import suppress_path
                            suppress_path(full_local_path)
                            os.remove(full_local_path)
                    
                    cur.execute("DELETE FROM files WHERE file_path = ?", (full_local_path,))
                    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (full_local_path,))
                    conn.commit()
    finally:
        _local_mutator.active = False
        conn.close()

    # Step 2: Concurrent file download downloads using _download_job_executor
    files_to_download = diff_payload.get("missing_files", []) + diff_payload.get("outdated_files", [])
    if files_to_download:
        print(f"[DOWNLOAD PIPELINE] Launching concurrent downloads for {len(files_to_download)} files...")
        futures = []
        for remote in files_to_download:
            futures.append(_download_job_executor.submit(_download_file_worker, remote, device_id))
            
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"[DOWNLOAD ERROR] Parallel download failed: {e}")


def download_and_write_chunk(idx: int, remote_hash: str, version_id: int,
                             temp_path: str, write_lock: threading.Lock,
                             aborted: threading.Event):
    """Worker task to download, decrypt, and write a single chunk to the temp file."""
    if aborted.is_set():
        return
        
    dl_ok, chunk_bytes = network_client.download_chunk(remote_hash, idx, version_id)
    if not dl_ok:
        raise Exception(f"Failed to download chunk {idx}")
    
    if aborted.is_set():
        return

    if config.encryption_key:
        try:
            nonce_in, tag, ciphertext = crypto_utils.unpack_encrypted(chunk_bytes)
            chunk_bytes = crypto_utils.decrypt_chunk(config.encryption_key, nonce_in, tag, ciphertext)
        except Exception as e:
            raise Exception(f"Failed to decrypt chunk {idx}: {e}")
            
    if aborted.is_set():
        return

    with write_lock:
        with open(temp_path, "r+b") as f:
            f.seek(idx * config.CHUNK_SIZE)
            f.write(chunk_bytes)


def reuse_local_chunk(idx: int, full_local_path: str, temp_path: str, write_lock: threading.Lock):
    """Worker task to read a local chunk from the existing file and copy it to the temp file."""
    offset = idx * config.CHUNK_SIZE
    with open(full_local_path, "rb") as f_in:
        f_in.seek(offset)
        chunk_bytes = f_in.read(config.CHUNK_SIZE)
        
    with write_lock:
        with open(temp_path, "r+b") as f_out:
            f_out.seek(offset)
            f_out.write(chunk_bytes)


def _delta_download_file(cur, conn, full_local_path: str, rel_path: str,
                         remote_hash: str, remote_chunk_hashes: list,
                         version_id: int, file_id: int, device_id: int):
    """
    Reconstruct a file using parallel delta sync: reuse local chunks and
    download missing ones from server without full RAM buffering.
    """
    # Get local chunk signatures for this file
    cur.execute("SELECT chunk_index, hash FROM chunk_signatures WHERE file_path = ? ORDER BY chunk_index",
                (full_local_path,))
    local_sigs = {row[0]: row[1] for row in cur.fetchall()}

    temp_path = full_local_path + ".tmp"
    
    # Initialize the temp file
    with open(temp_path, "wb") as f:
        pass

    write_lock = threading.Lock()
    download_aborted = threading.Event()
    futures = []
    
    download_count = 0
    reuse_count = 0

    for idx, remote_ch in enumerate(remote_chunk_hashes):
        if idx in local_sigs and local_sigs[idx] == remote_ch:
            # Reuse local chunk
            futures.append(_download_chunk_executor.submit(
                reuse_local_chunk, idx, full_local_path, temp_path, write_lock
            ))
            reuse_count += 1
        else:
            # Download chunk
            futures.append(_download_chunk_executor.submit(
                download_and_write_chunk, idx, remote_hash, version_id, temp_path, write_lock, download_aborted
            ))
            download_count += 1

    # Wait for all chunks to be written to temp file
    try:
        for future in as_completed(futures):
            if download_aborted.is_set():
                break
            try:
                future.result()
            except Exception as e:
                download_aborted.set()
                raise
    except Exception as e:
        print(f"[DELTA DOWNLOAD ERROR] Reconstruction failed for {rel_path}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return

    if download_aborted.is_set():
        print(f"[DELTA DOWNLOAD ERROR] Reconstruction aborted for {rel_path}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return

    print(f"[DELTA DOWNLOAD] {rel_path}: reused {reuse_count} chunks, downloaded {download_count} chunks")

    # Rename temp file to destination path
    from watcher import suppress_path
    suppress_path(full_local_path)
    
    if os.path.exists(full_local_path):
        try:
            os.remove(full_local_path)
        except OSError:
            pass
            
    os.rename(temp_path, full_local_path)

    # Update local metadata
    stat = os.stat(full_local_path)
    plaintext_hash = hash_utils.hash_file(full_local_path)
    
    cur.execute("""
        INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id, encrypted_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (full_local_path, plaintext_hash, stat.st_size, stat.st_mtime, version_id, remote_hash))

    # Update chunk signatures to store the encrypted chunk hashes
    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (full_local_path,))
    for idx, ch in enumerate(remote_chunk_hashes):
        cur.execute("""
            INSERT INTO chunk_signatures (file_path, chunk_index, hash)
            VALUES (?, ?, ?)
        """, (full_local_path, idx, ch))

    conn.commit()
    print(f"[DELTA DOWNLOAD SUCCESS] Reconstructed: {rel_path}")

    # Update server tracking mapping
    network_client.ack_sync(device_id, file_id, version_id)


def _heartbeat_worker():
    """Lightweight daemon thread that calls send_heartbeat every 60 seconds."""
    while not _stop_event.is_set():
        try:
            if not config.sync_suspended and network_client.health_check():
                device_id = _get_device_id()
                hb_success, pending_commands = network_client.send_heartbeat(device_id)
                if hb_success and pending_commands:
                    for cmd in pending_commands:
                        command_name = cmd.get("command")
                        cmd_id = cmd.get("id")
                        print(f"[SYNC ENGINE] Received remote command: {command_name}")
                        
                        if command_name == "WAKE":
                            print("🌟 WAKE SIGNAL RECEIVED FROM SERVER 🌟")
                            network_client.ack_command(device_id, cmd_id)
                        elif command_name == "REVOKE":
                            print("🚨 DEVICE ACCESS REVOKED BY SERVER 🚨 Wiping local data...")
                            conn = get_db_connection()
                            cur = conn.cursor()
                            cur.execute("DELETE FROM settings WHERE key IN ('access_token', 'device_id', 'encryption_key')")
                            conn.commit()
                            conn.close()
                            network_client.ack_command(device_id, cmd_id)
                            import sys
                            sys.exit(0)
                        else:
                            network_client.ack_command(device_id, cmd_id)
        except Exception as e:
            pass
        
        for _ in range(60):
            if _stop_event.is_set():
                break
            time.sleep(1)


_downstream_sync_lock = threading.Lock()

def run_downstream_sync_async(device_id: int):
    """Triggers downstream download sync process in background if not already running."""
    def target():
        if not _downstream_sync_lock.acquire(blocking=False):
            return
        try:
            process_downstream_downloads(device_id)
        except Exception as e:
            print(f"[DOWNLOAD PIPELINE CRASH]: {e}")
        finally:
            _downstream_sync_lock.release()

    t = threading.Thread(target=target, name="downstream-sync", daemon=True)
    t.start()


def stop_sync_loop():
    """Requests all background loops and threads to stop gracefully."""
    print("[SYNC ENGINE] Signaling background pools to shut down.")
    _stop_event.set()
    event_listener.sync_nudge.set()
    _upload_chunk_executor.shutdown(wait=False)
    _download_chunk_executor.shutdown(wait=False)
    _download_job_executor.shutdown(wait=False)


def start_sync_loop():
    """Background loop alternating between upload queues and downstream comparisons."""
    print("[SYNC ENGINE] Initializing transaction event loop.")
    _stop_event.clear()
    
    # Spawn the isolated background upload consumer pipeline with 4 parallel threads
    for i in range(4):
        t = threading.Thread(target=_upload_worker, name=f"upload-job-worker-{i}", daemon=True)
        t.start()
    
    # Spawn the heartbeat worker (runs every 60s)
    hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True)
    hb_thread.start()

    while not _stop_event.is_set():
        try:
            if config.sync_suspended:
                print("[SYNC ENGINE] Sync is suspended due to authentication error. Please login (python main.py login).")
                time.sleep(config.SYNC_INTERVAL_SECONDS)
                continue

            if network_client.health_check():
                device_id = _get_device_id()
                if device_id is None:
                    time.sleep(config.SYNC_INTERVAL_SECONDS)
                    continue

                # Process Downstream Phase in background asynchronously
                run_downstream_sync_async(device_id)

                # Process Local Outbound Changes Second (Week 5 Staging events)
                conn = get_db_connection()
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                cur.execute("SELECT * FROM events WHERE is_synced = 0 ORDER BY id ASC")
                pending_events = cur.fetchall()
                conn.close()

                if pending_events:
                    print(f"[DEBUG] Found {len(pending_events)} pending events at {time.time()}")
                
                for event in pending_events:
                    if _stop_event.is_set():
                        break
                        
                    event_id = event["id"]
                    if event_id in _in_flight_events:
                        continue

                    event_type = event["event_type"]
                    full_path = event["file_path"]
                    file_hash = event["hash"]

                    version_id = event["version_id"] if "version_id" in event.keys() else 0
                    timestamp = event["timestamp"]

                    # Compute clean tracking paths relative to root target
                    relative_path = os.path.relpath(full_path, config.WATCH_DIR).replace("\\", "/")
                    print(f"[SYNC] Upload Pipeline announcing: {relative_path} at {time.time()}")
                    
                    # Phase 1: Compute chunk hashes for large files
                    chunk_hashes = None
                    announced_file_hash = file_hash
                    if event_type != "deleted" and os.path.exists(full_path):
                        if config.encryption_key:
                            enc_file_hash, enc_chunk_hashes = get_prepared_encrypted_hashes(full_path, file_hash)
                            announced_file_hash = enc_file_hash
                            file_size = os.path.getsize(full_path)
                            if file_size >= config.CHUNK_THRESHOLD:
                                chunk_hashes = enc_chunk_hashes
                        else:
                            file_size = os.path.getsize(full_path)
                            if file_size >= config.CHUNK_THRESHOLD:
                                chunk_hashes = hash_utils.chunk_and_hash_file(full_path)
                    
                    success, response_data = network_client.announce_metadata(
                        relative_path, announced_file_hash, event_type, 
                        base_version_id=version_id, client_modified_at=timestamp,
                        chunk_hashes=chunk_hashes
                    )
                    if not success:
                        continue

                    if response_data.get("upload_required") and event_type != "deleted":
                        if not os.path.exists(full_path):
                            _mark_synced_db(event_id)
                            continue

                        file_size = os.path.getsize(full_path)
                        
                        # Phase 1: Extract missing_chunks from server response
                        missing_chunks = response_data.get("missing_chunks", None)
                        
                        job = UploadJob(
                            local_path=full_path,
                            remote_path=relative_path,
                            file_hash=announced_file_hash,
                            version_id=response_data.get("version_id", 0),
                            file_size=file_size,
                            event_id=event_id,
                            plaintext_hash=file_hash,
                            missing_chunks=missing_chunks,
                            file_id=response_data.get("file_id", 0)
                        )
                        _mark_in_flight(event_id)
                        upload_queue.put(job)
                    else:
                        _mark_synced_db(event_id)
            else:
                print("[SYNC ENGINE] Remote node sleeping/unreachable. Idle hold pattern.")
        except Exception as e:
            print(f"[SYNC ENGINE CRASH LOOP DETECTED]: {e}")
            
        if _stop_event.is_set():
            break
            
        # Wait up to SYNC_INTERVAL_SECONDS seconds, but wake immediately if SSE nudges us.
        event_listener.sync_nudge.wait(timeout=config.SYNC_INTERVAL_SECONDS)
        event_listener.sync_nudge.clear()

def main():
    """Direct entry diagnostic point if launched explicitly."""
    import diff_engine
    diff_engine.ensure_db()
    start_sync_loop()