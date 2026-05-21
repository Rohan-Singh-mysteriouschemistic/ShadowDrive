"""
sync_engine.py — Dual-direction Synchronization Core Engine (Week 6/7)
Manages outbound event queues and executes metadata diff reconstruction.
"""

import time
import sqlite3
import os
import threading
import queue
from dataclasses import dataclass

import network_client
import config
import hash_utils  # <--- WEEK 7 ADDITION: Needed for conflict state checking

@dataclass
class UploadJob:
    local_path: str
    remote_path: str
    file_hash: str
    version_id: int
    file_size: int
    event_id: int        
    retry_count: int = 0
    completed_chunks: set = None

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

# Thread-local storage flag to prevent downstream downloads from causing loop alerts
_local_mutator = threading.local()

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
            current_hash = hash_utils.hash_file(job.local_path)
            if current_hash != job.file_hash:
                print(f"[UPLOAD WORKER] Job for {job.remote_path} is obsolete (local hash changed from {job.file_hash[:8]} to {current_hash[:8] if current_hash else 'None'}). Discarding.")
                _mark_synced_db(job.event_id)
                _clear_in_flight(job.event_id)
                continue

            # Initialize chunk completion tracking for this job if not set
            if job.completed_chunks is None:
                job.completed_chunks = set()

            if job.file_size < config.CHUNK_THRESHOLD:
                success, data = network_client.upload_file(job.remote_path, job.local_path)
                if success:
                    print(f"[UPLOAD SUCCESS] {job.remote_path} (single-shot)")
                    _mark_synced_db(job.event_id)
                    _clear_in_flight(job.event_id)
                else:
                    _handle_failed_job(job, data)
            else:
                # Chunked upload workflow execution path
                total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE
                print(f"[UPLOAD CHUNKED] Spooling {total_chunks} parts for {job.remote_path} (already finished: {len(job.completed_chunks)})")
                
                all_chunks_succeeded = True
                last_error_data = {}
                for i in range(total_chunks):
                    if i in job.completed_chunks:
                        continue
                        
                    offset = i * config.CHUNK_SIZE
                    current_chunk_size = min(config.CHUNK_SIZE, job.file_size - offset)
                    
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

# ─── WEEK 6/7 DOWNLOAD PIPELINE logic ──────────────────────────────────────────

def process_downstream_downloads():
    """
    Fetches the server manifest map, calculates a diff against local metadata tables,
    and updates the local workspace folder through sequential block collection.
    Now includes Week 7 Conflict Detection!
    """
    success, diff_payload = network_client.get_metadata_diff(device_id=1)
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
                conn.commit()

        # Step 2: Evaluate inserts and modifications 
        files_to_download = diff_payload.get("missing_files", []) + diff_payload.get("outdated_files", [])
        for remote in files_to_download:
            rel_path = remote["file_path"]
            remote_hash = remote["hash"]
            version_id = remote["version_id"]
            file_id = remote["file_id"]
            storage_path = remote["storage_path"]

            full_local_path = os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep))

            # Query shadow database tracking records
            cur.execute("SELECT hash FROM files WHERE file_path = ?", (full_local_path,))
            row = cur.fetchone()

            # WEEK 7: SIMULTANEOUS EDIT CONFLICT DETECTION
            is_conflict = False
            db_hash = None
            if row is not None:
                db_hash = row[0]
                if db_hash != remote_hash:
                    # The server has a new version. Check if we ALSO modified our local file!
                    if os.path.exists(full_local_path):
                        current_local_hash = hash_utils.hash_file(full_local_path)
                        if current_local_hash and current_local_hash != db_hash:
                            is_conflict = True

            if row is None or db_hash != remote_hash:
                
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

                dl_ok, file_bytes = network_client.download_file(storage_path)
                if dl_ok:
                    with open(full_local_path, "wb") as f:
                        f.write(file_bytes)
                        
                    stat = os.stat(full_local_path)
                    cur.execute("""
                        INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (full_local_path, remote_hash, stat.st_size, stat.st_mtime, version_id))
                    conn.commit()
                    print(f"[DOWNLOAD SUCCESS] Materialized update onto filesystem: {rel_path}")
                    
                    # Update server tracking mapping
                    network_client.ack_sync(1, file_id, version_id)

    finally:
        _local_mutator.active = False
        conn.close()

def start_sync_loop():
    """Background loop alternating between upload queues and downstream comparisons."""
    print("[SYNC ENGINE] Initializing transaction event loop.")
    
    # Spawn the isolated background upload consumer pipeline
    t = threading.Thread(target=_upload_worker, daemon=True)
    t.start()

    while True:
        try:
            if network_client.health_check():
                # Process Downstream Phase First (Week 6 Download Step)
                process_downstream_downloads()

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
                    
                    success, response_data = network_client.announce_metadata(
                        relative_path, file_hash, event_type, 
                        base_version_id=version_id, client_modified_at=timestamp
                    )
                    if not success:
                        continue

                    if response_data.get("upload_required") and event_type != "deleted":
                        if not os.path.exists(full_path):
                            _mark_synced_db(event_id)
                            continue

                        file_size = os.path.getsize(full_path)
                        
                        # In case of conflict, server returns conflict_info. We can ignore it here because
                        # if upload_required is true, we must upload either the original file or the conflict copy.
                        # Wait, if we are the winner, we upload the file as normal. If we are the loser, we don't upload
                        # because the server actually expects the client to pull the conflict file. Wait, no,
                        # the server explicitly responds with upload_required=True and says which version is ours!
                        
                        job = UploadJob(
                            local_path=full_path,
                            remote_path=relative_path,
                            file_hash=file_hash,
                            version_id=response_data.get("version_id", 0),
                            file_size=file_size,
                            event_id=event_id
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