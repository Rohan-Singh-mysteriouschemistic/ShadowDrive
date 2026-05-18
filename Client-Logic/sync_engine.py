import time
import sqlite3
import os
import threading
import queue
from dataclasses import dataclass

import network_client
import config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "shadow.db")

@dataclass
class UploadJob:
    local_path: str
    remote_path: str
    file_hash: str
    version_id: int
    file_size: int
    event_id: int        # Added to mark_synced in DB
    retry_count: int = 0

upload_queue: queue.Queue = queue.Queue()

def _upload_worker():
    print("[UPLOAD WORKER] Started.")
    while True:
        job = upload_queue.get()
        try:
            if not os.path.exists(job.local_path):
                print(f"[UPLOAD WORKER] File disappeared: {job.local_path}")
                _mark_synced_db(job.event_id)
                upload_queue.task_done()
                continue
                
            if job.file_size < config.CHUNK_THRESHOLD:
                success, data = network_client.upload_file(job.remote_path, job.local_path)
                if success:
                    print(f"[UPLOAD SUCCESS] {job.remote_path} (single-shot)")
                    _mark_synced_db(job.event_id)
                else:
                    _handle_retry(job)
            else:
                success = _chunked_upload(job)
                if success:
                    print(f"[UPLOAD SUCCESS] {job.remote_path} (chunked)")
                    _mark_synced_db(job.event_id)
                else:
                    _handle_retry(job)
        except Exception as e:
            print(f"[UPLOAD WORKER ERROR] {e}")
            _handle_retry(job)
        finally:
            upload_queue.task_done()

def _chunked_upload(job: UploadJob) -> bool:
    total_chunks = (job.file_size + config.CHUNK_SIZE - 1) // config.CHUNK_SIZE
    print(f"[CHUNKED UPLOAD] {job.remote_path} -> {total_chunks} chunks")
    for i in range(total_chunks):
        offset = i * config.CHUNK_SIZE
        this_chunk_size = min(config.CHUNK_SIZE, job.file_size - offset)
        success, data = network_client.upload_chunk(
            local_path=job.local_path,
            version_id=job.version_id,
            chunk_index=i,
            total_chunks=total_chunks,
            file_hash=job.file_hash,
            offset=offset,
            chunk_size=this_chunk_size
        )
        if not success:
            print(f"[CHUNK FAILED] {i}/{total_chunks} for {job.remote_path}")
            return False
    return True

def _handle_retry(job: UploadJob):
    job.retry_count += 1
    if job.retry_count <= config.UPLOAD_MAX_RETRIES:
        print(f"[UPLOAD RETRY] {job.remote_path} attempt {job.retry_count} in {config.UPLOAD_RETRY_DELAY}s")
        time.sleep(config.UPLOAD_RETRY_DELAY)
        upload_queue.put(job)
    else:
        print(f"[UPLOAD FAILED] Dropping {job.remote_path} after max retries.")

def _mark_synced_db(event_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE events SET is_synced = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def start_sync_loop():
    print("[SYNC ENGINE] Started")
    worker_thread = threading.Thread(target=_upload_worker, name="UploadWorker", daemon=True)
    worker_thread.start()

    while True:
        try:
            if network_client.health_check():
                sync_pending_events()
            else:
                print("[NETWORK] Server unreachable")
        except Exception as e:
            print(f"[SYNC ENGINE ERROR] {e}")
        time.sleep(config.SYNC_INTERVAL_SECONDS)

def sync_pending_events():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM events WHERE is_synced = 0 ORDER BY id ASC")
    events = cursor.fetchall()

    if not events:
        conn.close()
        return

    print(f"[SYNC] Found {len(events)} pending events")

    for event in events:
        try:
            event_id = event["id"]
            event_type = event["event_type"]
            full_path = event["file_path"]
            file_hash = event["hash"]

            relative_path = os.path.basename(full_path)

            print(f"[SYNC] Processing: {relative_path}")
            success, response_data = network_client.announce_metadata(relative_path, file_hash, event_type)

            if not success:
                print(f"[SYNC] Announce failed for {relative_path}, will retry")
                continue

            if response_data.get("upload_required") and event_type != "deleted":
                if not os.path.exists(full_path):
                    print(f"[SYNC] File vanished before upload: {relative_path}")
                    _mark_synced_db(event_id)
                    continue

                file_size = os.path.getsize(full_path)
                job = UploadJob(
                    local_path=full_path,
                    remote_path=relative_path,
                    file_hash=file_hash,
                    version_id=response_data["version_id"],
                    file_size=file_size,
                    event_id=event_id
                )
                upload_queue.put(job)
                print(f"[SYNC] Queued upload for {relative_path}")
            else:
                print(f"[SYNC] Server acknowledged (no upload needed): {response_data.get('status')}")
                _mark_synced_db(event_id)

        except Exception as e:
            print(f"[EVENT ERROR] {e}")

    conn.close()