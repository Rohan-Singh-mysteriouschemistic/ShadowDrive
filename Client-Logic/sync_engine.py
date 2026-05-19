"""
sync_engine.py — Dual-direction Synchronization Core Engine (Week 6)
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

@dataclass
class UploadJob:
    local_path: str
    remote_path: str
    file_hash: str
    version_id: int
    file_size: int
    event_id: int        
    retry_count: int = 0

upload_queue: queue.Queue = queue.Queue()

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
            if not os.path.exists(job.local_path):
                print(f"[UPLOAD WORKER] File vanished before transit: {job.local_path}")
                _mark_synced_db(job.event_id)
                upload_queue.task_done()
                continue
                
            if job.file_size < config.CHUNK_THRESHOLD:
                success, data = network_client.upload_file(job.remote_path, job.local_path)
                if success:
                    print(f"[UPLOAD SUCCESS] {job.remote_path} (single-shot)")
                    _mark_synced_db(job.event_id)
                else:
                    _handle_failed_job(job)
            else:
                # Chunked upload workflow execution path
                total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE
                print(f"[UPLOAD CHUNKED] Spooling {total_chunks} parts for {job.remote_path}")
                
                all_chunks_succeeded = True
                for i in range(total_chunks):
                    offset = i * config.CHUNK_SIZE
                    current_chunk_size = min(config.CHUNK_SIZE, job.file_size - offset)
                    
                    chunk_ok, _ = network_client.upload_chunk(
                        local_path=job.local_path,
                        offset=offset,
                        chunk_size=current_chunk_size,
                        chunk_index=i,
                        total_chunks=total_chunks,
                        file_hash=job.file_hash,
                        version_id=job.version_id
                    )
                    if not chunk_ok:
                        print(f"[UPLOAD CHUNKED] Failure on part index {i}")
                        all_chunks_succeeded = False
                        break
                
                if all_chunks_succeeded:
                    print(f"[UPLOAD CHUNKED SUCCESS] Completed all blocks for {job.remote_path}")
                    _mark_synced_db(job.event_id)
                else:
                    _handle_failed_job(job)
                    
        except Exception as e:
            print(f"[UPLOAD ERROR] Unexpected crash in transiting worker: {e}")
            _handle_failed_job(job)
        finally:
            upload_queue.task_done()

def _handle_failed_job(job: UploadJob):
    """Processes backoff retry increments on critical connection dropped states."""
    if job.retry_count < config.UPLOAD_MAX_RETRIES:
        job.retry_count += 1
        print(f"[RETRY QUEUE] Queued retry #{job.retry_count} for {job.remote_path}")
        time.sleep(config.RETRY_BACKOFF_SECONDS)
        upload_queue.put(job)
    else:
        print(f"[FATAL FAILURE] Maximum fallback constraints hit for {job.remote_path}")

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

# ─── WEEK 6 DOWNLOAD PIPELINE logic ──────────────────────────────────────────

def process_downstream_downloads():
    """
    Fetches the server manifest map, calculates a diff against local metadata tables,
    and updates the local workspace folder through sequential block collection.
    """
    success, server_files = network_client.get_server_metadata()
    if not success:
        return

    conn = sqlite3.connect(config.DB_PATH)
    cur = conn.cursor()

    # Step 1: Detect deleted items on server to match locally
    server_paths = {f["file_path"] for f in server_files}
    cur.execute("SELECT file_path FROM files")
    local_files = [row[0] for row in cur.fetchall()]

    _local_mutator.active = True  # Mute local event logging from handling this disk action
    try:
        for path in local_files:
            # Reconstruct relative mapping for comparison checks
            rel_path = os.path.relpath(path, config.WATCH_DIR).replace("\\", "/")
            if rel_path not in server_paths:
                print(f"[DOWNLOAD PIPELINE] Server deleted file, removing locally: {rel_path}")
                if os.path.exists(path):
                    os.remove(path)
                cur.execute("DELETE FROM files WHERE file_path = ?", (path,))
                conn.commit()

        # Step 2: Evaluate inserts and modifications 
        for remote in server_files:
            rel_path = remote["file_path"]
            remote_hash = remote["file_hash"]
            remote_size = remote["size"]
            version_id = remote.get("version_id", 1)
            total_chunks = remote.get("total_chunks", 1)

            full_local_path = os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep))

            # Query shadow database tracking records
            cur.execute("SELECT hash FROM files WHERE file_path = ?", (full_local_path,))
            row = cur.fetchone()

            if row is None or row[0] != remote_hash:
                print(f"[DOWNLOAD PIPELINE] Inconsistency detected. Pulling: {rel_path}")
                os.makedirs(os.path.dirname(full_local_path), exist_ok=True)

                download_success = False
                # Scenario Alpha: Match single shot or multi-chunk reconstruct rule
                if remote_size < config.CHUNK_THRESHOLD:
                    dl_ok, file_bytes = network_client.download_file(rel_path)
                    if dl_ok:
                        with open(full_local_path, "wb") as f:
                            f.write(file_bytes)
                        download_success = True
                else:
                    # Multi-part chunk re-assembly
                    tmp_file_path = full_local_path + ".tmp"
                    try:
                        with open(tmp_file_path, "wb") as f_out:
                            for idx in range(total_chunks):
                                chk_ok, chunk_bytes = network_client.download_chunk(remote_hash, idx, version_id)
                                if not chk_ok:
                                    raise IOError(f"Missing segment tracking block {idx}")
                                f_out.write(chunk_bytes)
                        
                        if os.path.exists(full_local_path):
                            os.remove(full_local_path)
                        os.rename(tmp_file_path, full_local_path)
                        download_success = True
                    except Exception as e:
                        print(f"[DOWNLOAD ERROR] Reconstruction failed for {rel_path}: {e}")
                        if os.path.exists(tmp_file_path):
                            os.remove(tmp_file_path)

                if download_success:
                    # Record newly matched metadata tracking state
                    stat = os.stat(full_local_path)
                    cur.execute("""
                        INSERT OR REPLACE INTO files (file_path, hash, size, last_modified)
                        VALUES (?, ?, ?, ?)
                    """, (full_local_path, remote_hash, stat.st_size, stat.st_mtime))
                    conn.commit()
                    print(f"[DOWNLOAD SUCCESS] Materialized update onto filesystem: {rel_path}")

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
                    event_type = event["event_type"]
                    full_path = event["file_path"]
                    file_hash = event["hash"]

                    # Compute clean tracking paths relative to root target
                    relative_path = os.path.relpath(full_path, config.WATCH_DIR).replace("\\", "/")
                    print(f"[SYNC] Upload Pipeline announcing: {relative_path}")
                    
                    success, response_data = network_client.announce_metadata(relative_path, file_hash, event_type)
                    if not success:
                        continue

                    if response_data.get("upload_required") and event_type != "deleted":
                        if not os.path.exists(full_path):
                            _mark_synced_db(event_id)
                            continue

                        file_size = os.path.getsize(full_path)
                        job = UploadJob(
                            local_path=full_path,
                            remote_path=relative_path,
                            file_hash=file_hash,
                            version_id=response_data.get("version_id", 0),
                            file_size=file_size,
                            event_id=event_id
                        )
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