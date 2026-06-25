"""
sync_engine.py — Synchronization Orchestrator

Coordinates the upload pipeline, download pipeline, and heartbeat worker.
All heavy logic has been extracted to uploader.py, downloader.py, and heartbeat.py.
"""

import os
import sqlite3
import threading
import time

import config
import event_listener
import hash_utils
import network_client
from downloader import run_downstream_sync_async
from heartbeat import get_device_id, heartbeat_worker
from loguru import logger
from state import _stop_event
from uploader import (
    UploadJob,
    get_prepared_encrypted_hashes,
    is_in_flight,
    mark_in_flight,
    mark_synced_db,
    upload_queue,
    upload_worker,
)

from database import get_connection


def _process_pending_uploads(device_id: int):
    """Read pending events from local DB and enqueue upload jobs."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM events WHERE is_synced = 0 ORDER BY id ASC")
    pending_events = cur.fetchall()

    if pending_events:
        logger.debug("Found {} pending events", len(pending_events))

    for event in pending_events:
        if _stop_event.is_set():
            break

        event_id = event["id"]
        if is_in_flight(event_id):
            continue

        event_type = event["event_type"]
        full_path = event["file_path"]
        file_hash = event["hash"]
        version_id = event["version_id"] if "version_id" in event.keys() else 0
        timestamp = event["timestamp"]

        relative_path = os.path.relpath(full_path, config.WATCH_DIR).replace("\\", "/")
        logger.info("Announcing: {}", relative_path)

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
                mark_synced_db(event_id)
                continue

            file_size = os.path.getsize(full_path)
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
                file_id=response_data.get("file_id", 0),
            )
            mark_in_flight(event_id, job)
            upload_queue.put(job)
        else:
            mark_synced_db(event_id)


def start_sync_loop():
    """Main sync loop orchestrating upload, download, and heartbeat pipelines."""
    logger.info("Sync engine initialized.")

    _stop_event.clear()

    # Spawn upload workers (4 parallel threads)
    for i in range(4):
        t = threading.Thread(target=upload_worker, name=f"upload-job-worker-{i}", daemon=True)
        t.start()

    # Spawn heartbeat worker (runs every 60s)
    hb_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    hb_thread.start()

    while not _stop_event.is_set():
        try:
            if config.sync_suspended:
                logger.warning("Sync suspended — please login.")
                time.sleep(config.SYNC_INTERVAL_SECONDS)
                continue

            if network_client.health_check():
                device_id = get_device_id()
                if device_id is None:
                    time.sleep(config.SYNC_INTERVAL_SECONDS)
                    continue

                # Phase 1: Process downstream downloads asynchronously
                run_downstream_sync_async(device_id)

                # Phase 2: Process local outbound changes
                _process_pending_uploads(device_id)
            else:
                logger.debug("Server unreachable. Idle.")
        except Exception as e:
            logger.error("Sync loop error: {}", e)

        if _stop_event.is_set():
            break

        event_listener.sync_nudge.wait(timeout=config.SYNC_INTERVAL_SECONDS)
        event_listener.sync_nudge.clear()


def stop_sync_loop():
    """Signal all background loops and threads to stop gracefully."""
    logger.info("Sync engine shutting down.")
    _stop_event.set()
    event_listener.sync_nudge.set()


def main():
    """Entry point."""
    import diff_engine
    diff_engine.ensure_db()
    start_sync_loop()
