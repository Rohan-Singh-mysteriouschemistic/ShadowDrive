"""
sync_engine.py — Dual-direction Synchronization Core Engine (Week 6/7 + Phase 1 Delta Sync)
Manages outbound event queues and executes metadata diff reconstruction.
"""

import time
import sqlite3
import os
import threading
import queue
from dataclasses import dataclass, field

import network_client
import config
import hash_utils  # <--- WEEK 7 ADDITION: Needed for conflict state checking
import crypto_utils

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

upload_queue: queue.Queue = queue.Queue()

# Thread-safe in-flight tracking set to prevent queue bloat
_in_flight_events = set()
_in_flight_lock = threading.Lock()

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

def get_or_create_nonces(file_path: str, plaintext_hash: str, total_chunks: int) -> list[bytes]:
    """
    Look up or generate the 12-byte nonces for each chunk of a file.
    To ensure deterministic behavior on retries, we persist these nonces in the 
    `pending_chunk_uploads` table along with the plaintext_hash.
    """
    import os
    conn = sqlite3.connect(config.DB_PATH)
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
    conn.close()
    return nonces


def prepare_encrypted_payload(full_path: str, plaintext_hash: str) -> tuple[str, list[str], list[bytes]]:
    """
    Encrypt the file chunks using config.encryption_key.
    Returns:
        encrypted_file_hash: SHA-256 hex of the concatenated encrypted chunks.
        encrypted_chunk_hashes: List of SHA-256 hex of each encrypted chunk.
        encrypted_chunks_data: List of raw bytes of packed encrypted chunks.
    """
    import hashlib
    
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
            
    nonces = get_or_create_nonces(full_path, plaintext_hash, total_chunks)
    
    encrypted_chunks_data = []
    encrypted_chunk_hashes = []
    
    with open(full_path, "rb") as f:
        for i in range(total_chunks):
            chunk_plain = f.read(chunk_sizes[i])
            nonce = nonces[i]
            nonce_out, tag, ciphertext = crypto_utils.encrypt_chunk(config.encryption_key, chunk_plain, nonce)
            packed = crypto_utils.pack_encrypted(nonce_out, tag, ciphertext)
            
            encrypted_chunks_data.append(packed)
            chunk_hash = hashlib.sha256(packed).hexdigest()
            encrypted_chunk_hashes.append(chunk_hash)
            
    full_encrypted_data = b"".join(encrypted_chunks_data)
    encrypted_file_hash = hashlib.sha256(full_encrypted_data).hexdigest()
    
    return encrypted_file_hash, encrypted_chunk_hashes, encrypted_chunks_data


def finalize_local_db_after_upload(full_path: str, plaintext_hash: str, version_id: int):
    """
    Once an upload succeeds and the server registers the version, finalize
    local shadow.db tracking tables: version_id, encrypted_hash, and chunk_signatures.
    """
    conn = sqlite3.connect(config.DB_PATH)
    cur = conn.cursor()
    
    if config.encryption_key:
        enc_file_hash, enc_chunk_hashes, _ = prepare_encrypted_payload(full_path, plaintext_hash)
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
    while True:
        job = upload_queue.get()
        try:
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

            # Prepare encrypted payload if encryption is active
            enc_file_hash = None
            enc_chunk_hashes = None
            enc_chunks_data = None
            if config.encryption_key:
                enc_file_hash, enc_chunk_hashes, enc_chunks_data = prepare_encrypted_payload(job.local_path, expected_plain_hash)

            if job.file_size < config.CHUNK_THRESHOLD:
                if config.encryption_key:
                    success, data = network_client.upload_file(job.remote_path, job.local_path, data=enc_chunks_data[0])
                else:
                    success, data = network_client.upload_file(job.remote_path, job.local_path)
                if success:
                    print(f"[UPLOAD SUCCESS] {job.remote_path} (single-shot)")
                    version_id = data.get("version_id", 0)
                    finalize_local_db_after_upload(job.local_path, expected_plain_hash, version_id)
                    _mark_synced_db(job.event_id)
                    _clear_in_flight(job.event_id)
                else:
                    _handle_failed_job(job, data)
            else:
                # Chunked upload workflow execution path
                total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE
                
                # Phase 1 Delta Sync: Determine which chunks actually need uploading
                if job.missing_chunks is not None:
                    chunks_to_upload = set(job.missing_chunks)
                    skipped = total_chunks - len(chunks_to_upload)
                    if skipped > 0:
                        print(f"[DELTA SYNC] Skipping {skipped}/{total_chunks} unchanged chunks for {job.remote_path}")
                else:
                    # Fallback: upload all chunks (no delta info from server)
                    chunks_to_upload = set(range(total_chunks))
                
                print(f"[UPLOAD CHUNKED] Spooling {len(chunks_to_upload)}/{total_chunks} parts for {job.remote_path} (already finished: {len(job.completed_chunks)})")
                
                all_chunks_succeeded = True
                last_error_data = {}
                for i in range(total_chunks):
                    # Skip chunks the server already has (delta sync)
                    if i not in chunks_to_upload:
                        continue
                    if i in job.completed_chunks:
                        continue
                        
                    offset = i * config.CHUNK_SIZE
                    current_chunk_size = min(config.CHUNK_SIZE, job.file_size - offset)
                    
                    if config.encryption_key:
                        chunk_ok, chunk_data = network_client.upload_chunk(
                            local_path=job.local_path,
                            offset=offset,
                            chunk_size=current_chunk_size,
                            chunk_index=i,
                            total_chunks=total_chunks,
                            file_hash=enc_file_hash,
                            version_id=job.version_id,
                            data=enc_chunks_data[i]
                        )
                    else:
                        chunk_ok, chunk_data = network_client.upload_chunk(
                            local_path=job.local_path,
                            offset=offset,
                            chunk_size=current_chunk_size,
                            chunk_index=i,
                            total_chunks=total_chunks,
                            file_hash=job.file_hash,
                            version_id=job.version_id
                        )
                    if chunk_ok:
                        job.completed_chunks.add(i)
                    else:
                        print(f"[UPLOAD CHUNKED] Failure on part index {i}/{total_chunks}")
                        all_chunks_succeeded = False
                        last_error_data = chunk_data
                        break
                
                if all_chunks_succeeded:
                    print(f"[UPLOAD CHUNKED SUCCESS] Completed all blocks for {job.remote_path}")
                    finalize_local_db_after_upload(job.local_path, expected_plain_hash, job.version_id)
                    _mark_synced_db(job.event_id)
                    _clear_in_flight(job.event_id)
                else:
                    _handle_failed_job(job, last_error_data)
                    
        except Exception as e:
            print(f"[UPLOAD ERROR] Unexpected crash in transiting worker: {e}")
            _handle_failed_job(job, {"error": str(e), "retriable": True})
        finally:
            upload_queue.task_done()

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
        conn = sqlite3.connect(config.DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE events SET is_synced = 1 WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"[DB ERROR] Mark synced exception: {e}")

# ─── WEEK 6/7 DOWNLOAD PIPELINE logic + Phase 1 Delta Download ──────────────

def _get_device_id() -> int:
    """Gets device_id from settings table, generating a unique random one if absent."""
    import random
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("SELECT value FROM settings WHERE key = 'device_id'")
        row = cur.fetchone()
        if row:
            device_id = int(row[0])
        else:
            # Generate random 6-digit device_id
            device_id = random.randint(100000, 999999)
            cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('device_id', ?)", (str(device_id),))
            conn.commit()
            print(f"[SYNC ENGINE] Generated new unique device_id: {device_id}")
        conn.close()
        return device_id
    except Exception as e:
        print(f"[SYNC ENGINE] Error getting/generating device_id: {e}. Defaulting to 1.")
        return 1


def process_downstream_downloads(device_id: int):
    """
    Fetches the server manifest map, calculates a diff against local metadata tables,
    and updates the local workspace folder through sequential block collection.
    Now includes Week 7 Conflict Detection and Phase 1 Delta Download Reconstruction!
    """
    success, diff_payload = network_client.get_metadata_diff(device_id=device_id)
    if not success:
        return

    conn = sqlite3.connect(config.DB_PATH)
    cur = conn.cursor()

    _local_mutator.active = True  # Mute local event logging from handling this disk action
    try:
        deleted_files = diff_payload.get("deleted_files", [])
        for rel_path in deleted_files:
            full_local_path = os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep))
            
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
                        os.remove(full_local_path)
                
                cur.execute("DELETE FROM files WHERE file_path = ?", (full_local_path,))
                cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (full_local_path,))
                conn.commit()

        # Step 2: Evaluate inserts and modifications 
        files_to_download = diff_payload.get("missing_files", []) + diff_payload.get("outdated_files", [])
        for remote in files_to_download:
            rel_path = remote["file_path"]
            remote_hash = remote["hash"]
            version_id = remote["version_id"]
            file_id = remote["file_id"]
            storage_path = remote["storage_path"]
            remote_chunk_hashes = remote.get("chunk_hashes", [])

            full_local_path = os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep))

            # Query shadow database tracking records
            try:
                cur.execute("SELECT hash, encrypted_hash FROM files WHERE file_path = ?", (full_local_path,))
                row = cur.fetchone()
            except sqlite3.OperationalError:
                # Fallback if DB not fully migrated
                cur.execute("SELECT hash FROM files WHERE file_path = ?", (full_local_path,))
                row = cur.fetchone()
                if row:
                    row = (row[0], None)

            # WEEK 7: SIMULTANEOUS EDIT CONFLICT DETECTION
            is_conflict = False
            db_plain_hash = None
            db_enc_hash = None
            if row is not None:
                db_plain_hash = row[0]
                db_enc_hash = row[1]
                
                # Check for updates: compare remote (encrypted) hash to stored encrypted hash
                target_db_hash = db_enc_hash if (db_enc_hash and config.encryption_key) else db_plain_hash
                if target_db_hash != remote_hash:
                    # The server has a new version. Check if we ALSO modified our local file!
                    if os.path.exists(full_local_path):
                        current_local_hash = hash_utils.hash_file(full_local_path)
                        if current_local_hash and current_local_hash != db_plain_hash:
                            is_conflict = True

            target_db_hash = db_enc_hash if (db_enc_hash and config.encryption_key) else db_plain_hash
            if row is None or target_db_hash != remote_hash:
                
                # Handle the Conflict Phase Before Downloading
                if is_conflict:
                    timestamp = int(time.time())
                    root, ext = os.path.splitext(full_local_path)
                    conflict_path = f"{root}_conflict_{timestamp}{ext}"
                    print(f"[CONFLICT DETECTED] Simultaneous edits on {rel_path}")
                    print(f" -> Moving your local work to: {os.path.basename(conflict_path)}")
                    os.rename(full_local_path, conflict_path)
                else:
                    print(f"[DOWNLOAD PIPELINE] Inconsistency detected. Pulling: {rel_path}")

                os.makedirs(os.path.dirname(full_local_path), exist_ok=True)

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
                                continue

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

    finally:
        _local_mutator.active = False
        conn.close()


def _delta_download_file(cur, conn, full_local_path: str, rel_path: str,
                         remote_hash: str, remote_chunk_hashes: list,
                         version_id: int, file_id: int, device_id: int):
    """
    Reconstruct a file using delta sync: reuse matching local chunks and
    download only the missing ones from the server.
    """
    # Get local chunk signatures for this file
    cur.execute("SELECT chunk_index, hash FROM chunk_signatures WHERE file_path = ? ORDER BY chunk_index",
                (full_local_path,))
    local_sigs = {row[0]: row[1] for row in cur.fetchall()}

    # Determine which remote chunks we already have locally
    chunks_data = {}
    download_count = 0
    reuse_count = 0

    for idx, remote_ch in enumerate(remote_chunk_hashes):
        if idx in local_sigs and local_sigs[idx] == remote_ch:
            # Reuse local chunk — read it from the existing file
            try:
                offset = idx * config.CHUNK_SIZE
                with open(full_local_path, "rb") as f:
                    f.seek(offset)
                    chunk_bytes = f.read(config.CHUNK_SIZE)
                chunks_data[idx] = chunk_bytes
                reuse_count += 1
            except OSError:
                # Local file unreadable, must download
                dl_ok, chunk_bytes = network_client.download_chunk(remote_hash, idx, version_id)
                if dl_ok:
                    if config.encryption_key:
                        try:
                            nonce_in, tag, ciphertext = crypto_utils.unpack_encrypted(chunk_bytes)
                            chunk_bytes = crypto_utils.decrypt_chunk(config.encryption_key, nonce_in, tag, ciphertext)
                        except Exception as e:
                            print(f"[CRYPTO ERROR] Failed to decrypt chunk {idx} for {rel_path}: {e}")
                            return
                    chunks_data[idx] = chunk_bytes
                    download_count += 1
                else:
                    print(f"[DELTA DOWNLOAD] Failed to download chunk {idx} for {rel_path}")
                    return
        else:
            # Chunk is different or doesn't exist locally — download it
            dl_ok, chunk_bytes = network_client.download_chunk(remote_hash, idx, version_id)
            if dl_ok:
                if config.encryption_key:
                    try:
                        nonce_in, tag, ciphertext = crypto_utils.unpack_encrypted(chunk_bytes)
                        chunk_bytes = crypto_utils.decrypt_chunk(config.encryption_key, nonce_in, tag, ciphertext)
                    except Exception as e:
                        print(f"[CRYPTO ERROR] Failed to decrypt chunk {idx} for {rel_path}: {e}")
                        return
                chunks_data[idx] = chunk_bytes
                download_count += 1
            else:
                print(f"[DELTA DOWNLOAD] Failed to download chunk {idx} for {rel_path}")
                return

    print(f"[DELTA DOWNLOAD] {rel_path}: reused {reuse_count} chunks, downloaded {download_count} chunks")

    # Reconstruct the file from chunks in order
    with open(full_local_path, "wb") as f:
        for idx in range(len(remote_chunk_hashes)):
            f.write(chunks_data[idx])

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


def start_sync_loop():
    """Background loop alternating between upload queues and downstream comparisons."""
    print("[SYNC ENGINE] Initializing transaction event loop.")
    
    # Spawn the isolated background upload consumer pipeline
    t = threading.Thread(target=_upload_worker, daemon=True)
    t.start()

    while True:
        try:
            if config.sync_suspended:
                print("[SYNC ENGINE] Sync is suspended due to authentication error. Please login (python main.py login).")
                time.sleep(config.SYNC_INTERVAL_SECONDS)
                continue

            if network_client.health_check():
                device_id = _get_device_id()
                # Process Downstream Phase First (Week 6 Download Step)
                process_downstream_downloads(device_id)

                # Process Local Outbound Changes Second (Week 5 Staging events)
                conn = sqlite3.connect(config.DB_PATH)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                cur.execute("SELECT * FROM events WHERE is_synced = 0 ORDER BY id ASC")
                pending_events = cur.fetchall()
                conn.close()

                for event in pending_events:
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
                    print(f"[SYNC] Upload Pipeline announcing: {relative_path}")
                    
                    # Phase 1: Compute chunk hashes for large files
                    chunk_hashes = None
                    announced_file_hash = file_hash
                    if event_type != "deleted" and os.path.exists(full_path):
                        if config.encryption_key:
                            enc_file_hash, enc_chunk_hashes, _ = prepare_encrypted_payload(full_path, file_hash)
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
                            missing_chunks=missing_chunks
                        )
                        _mark_in_flight(event_id)
                        upload_queue.put(job)
                    else:
                        _mark_synced_db(event_id)
            else:
                print("[SYNC ENGINE] Remote node sleeping/unreachable. Idle hold pattern.")
        except Exception as e:
            print(f"[SYNC ENGINE CRASH LOOP DETECTED]: {e}")
            
        time.sleep(config.SYNC_INTERVAL_SECONDS)

def main():
    """Direct entry diagnostic point if launched explicitly."""
    import diff_engine
    diff_engine.ensure_db()
    start_sync_loop()