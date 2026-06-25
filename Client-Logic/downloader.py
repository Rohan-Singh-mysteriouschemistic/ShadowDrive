"""
downloader.py — Downstream Download Pipeline

Fetches server manifest, calculates diff, downloads missing/outdated files.
Handles conflict detection and parallel delta sync reconstruction.
Extracted from sync_engine.py for maintainability.
"""

import os
import shutil
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import config
import crypto_utils
import hash_utils
import network_client
from loguru import logger
from state import PathLock, _downstream_sync_lock, set_local_mutation

from database import get_connection

# Dedicated executors for parallel downloads
_download_chunk_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="download-chunk")
_download_job_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="download-job")


def _get_device_id() -> Optional[int]:
    """Gets device_id from the local settings table."""
    from network_client import _get_setting
    dev_id = _get_setting("device_id")
    return int(dev_id) if dev_id else None


def _download_file_worker(remote: dict, device_id: int):
    """Process a single file download including conflict resolution, download, and DB updates."""
    rel_path = remote["file_path"]
    remote_hash = remote["hash"]
    version_id = remote["version_id"]
    file_id = remote["file_id"]
    storage_path = remote["storage_path"]
    remote_chunk_hashes = remote.get("chunk_hashes", [])

    full_local_path = os.path.normpath(os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep)))

    with PathLock(full_local_path):
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT hash, encrypted_hash, version_id FROM files WHERE file_path = ?", (full_local_path,))
            row = cur.fetchone()
        except sqlite3.OperationalError:
            cur.execute("SELECT hash FROM files WHERE file_path = ?", (full_local_path,))
            row = cur.fetchone()
            if row:
                row = (row[0], None, 0)

        # Conflict detection
        is_conflict = False
        db_plain_hash = None
        db_enc_hash = None
        db_version_id = 0
        if row is not None:
            db_plain_hash = row[0]
            db_enc_hash = row[1]
            db_version_id = row[2] if len(row) > 2 else 0

            if db_version_id >= version_id:
                logger.debug("Skipping {} (local v{} >= remote v{})", rel_path, db_version_id, version_id)
                network_client.ack_sync(device_id, file_id, db_version_id)
                conn.close()
                return

            target_db_hash = db_enc_hash if (db_enc_hash and config.encryption_key) else db_plain_hash
            if target_db_hash != remote_hash:
                cur.execute("SELECT 1 FROM events WHERE file_path = ? AND is_synced = 0", (full_local_path,))
                if cur.fetchone():
                    is_conflict = True

        target_db_hash = db_enc_hash if (db_enc_hash and config.encryption_key) else db_plain_hash
        if row is None or target_db_hash != remote_hash:

            if is_conflict:
                root, ext = os.path.splitext(full_local_path)
                conflict_path = f"{root} (Conflicted copy){ext}"
                logger.warning("Simultaneous edits on {}. Preserving local as: {}", rel_path, os.path.basename(conflict_path))
                shutil.copy2(full_local_path, conflict_path)
            else:
                logger.info("Pulling: {}", rel_path)

            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)

            from watcher import suppress_path
            suppress_path(full_local_path)

            if remote_chunk_hashes:
                _delta_download_file(cur, conn, full_local_path, rel_path,
                                     remote_hash, remote_chunk_hashes,
                                     version_id, file_id, device_id)
            else:
                _full_download_file(cur, conn, full_local_path, rel_path,
                                    storage_path, remote_hash, version_id, file_id, device_id)
        else:
            logger.info("Local file '{}' hash matches remote, skipping content download and updating local metadata to version {}", rel_path, version_id)
            cur.execute("UPDATE files SET version_id = ? WHERE file_path = ?", (version_id, full_local_path))
            conn.commit()
            network_client.ack_sync(device_id, file_id, version_id)

        conn.close()


def _full_download_file(cur, conn, full_local_path: str, rel_path: str,
                        storage_path: str, remote_hash: str,
                        version_id: int, file_id: int, device_id: int):
    """Download a file as a single-shot transfer."""
    dl_ok, file_bytes = network_client.download_file(storage_path)
    if not dl_ok:
        logger.error("Failed to download {}", rel_path)
        return

    if config.encryption_key:
        try:
            nonce_in, tag, ciphertext = crypto_utils.unpack_encrypted(file_bytes)
            file_bytes = crypto_utils.decrypt_chunk(config.encryption_key, nonce_in, tag, ciphertext)
            if config.COMPRESSION == "zlib":
                file_bytes = crypto_utils.decompress_after_decrypt(file_bytes)
        except Exception as e:
            logger.error("Decryption failed for {}: {}", rel_path, e)
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
    logger.success("Downloaded: {}", rel_path)
    network_client.ack_sync(device_id, file_id, version_id)


def process_downstream_downloads(device_id: int):
    """Fetch server manifest, compare with local state, download changes."""
    success, diff_payload = network_client.get_metadata_diff(device_id=device_id)
    if not success:
        return

    conn = get_connection()
    cur = conn.cursor()

    set_local_mutation(True)
    try:
        deleted_files = diff_payload.get("deleted_files", [])
        for rel_path in deleted_files:
            full_local_path = os.path.normpath(os.path.join(config.WATCH_DIR, rel_path.replace("/", os.sep)))

            with PathLock(full_local_path):
                try:
                    cur.execute("SELECT hash, version_id FROM files WHERE file_path = ?", (full_local_path,))
                except sqlite3.OperationalError:
                    cur.execute("SELECT hash FROM files WHERE file_path = ?", (full_local_path,))
                row = cur.fetchone()

                if row:
                    db_hash = row[0]
                    current_local_hash = hash_utils.hash_file(full_local_path)

                    if current_local_hash and current_local_hash != db_hash:
                        timestamp = int(time.time())
                        root, ext = os.path.splitext(full_local_path)
                        conflict_path = f"{root}_conflict_{timestamp}{ext}"
                        logger.warning("Server deleted '{}', but local was modified. Preserving as: {}",
                                       rel_path, os.path.basename(conflict_path))
                        os.rename(full_local_path, conflict_path)
                    else:
                        logger.info("Server deleted file, removing locally: {}", rel_path)
                        if os.path.exists(full_local_path):
                            from watcher import suppress_path
                            suppress_path(full_local_path)
                            os.remove(full_local_path)

                    cur.execute("DELETE FROM files WHERE file_path = ?", (full_local_path,))
                    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (full_local_path,))
                    conn.commit()
    finally:
        set_local_mutation(False)
        conn.close()

    # Step 2: Concurrent file downloads
    files_to_download = diff_payload.get("missing_files", []) + diff_payload.get("outdated_files", [])
    if files_to_download:
        logger.info("Launching concurrent downloads for {} files...", len(files_to_download))
        futures = []
        for remote in files_to_download:
            futures.append(_download_job_executor.submit(_download_file_worker, remote, device_id))

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error("Parallel download failed: {}", e)


# ─── Delta Download ───────────────────────────────────────────────────────────

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
            if config.COMPRESSION == "zlib":
                chunk_bytes = crypto_utils.decompress_after_decrypt(chunk_bytes)
        except Exception as e:
            raise Exception(f"Failed to decrypt chunk {idx}: {e}")

    if aborted.is_set():
        return

    with write_lock:
        with open(temp_path, "r+b") as f:
            f.seek(idx * config.CHUNK_SIZE)
            f.write(chunk_bytes)


def reuse_local_chunk(idx: int, full_local_path: str, temp_path: str, write_lock: threading.Lock):
    """Worker task to read a local chunk and copy it to the temp file."""
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
    """Reconstruct a file using parallel delta sync."""
    cur.execute("SELECT chunk_index, hash FROM chunk_signatures WHERE file_path = ? ORDER BY chunk_index",
                (full_local_path,))
    local_sigs = {row[0]: row[1] for row in cur.fetchall()}

    temp_path = full_local_path + ".tmp"

    open(temp_path, "wb").close()

    write_lock = threading.Lock()
    download_aborted = threading.Event()
    futures = []

    download_count = 0
    reuse_count = 0

    for idx, remote_ch in enumerate(remote_chunk_hashes):
        if idx in local_sigs and local_sigs[idx] == remote_ch:
            futures.append(_download_chunk_executor.submit(
                reuse_local_chunk, idx, full_local_path, temp_path, write_lock
            ))
            reuse_count += 1
        else:
            futures.append(_download_chunk_executor.submit(
                download_and_write_chunk, idx, remote_hash, version_id, temp_path, write_lock, download_aborted
            ))
            download_count += 1

    try:
        for future in as_completed(futures):
            if download_aborted.is_set():
                break
            try:
                future.result()
            except Exception:
                download_aborted.set()
                raise
    except Exception as e:
        logger.error("Delta download reconstruction failed for {}: {}", rel_path, e)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return

    if download_aborted.is_set():
        logger.error("Delta download aborted for {}", rel_path)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return

    logger.info("Delta download {}: reused {}, downloaded {}", rel_path, reuse_count, download_count)

    from watcher import suppress_path
    suppress_path(full_local_path)

    if os.path.exists(full_local_path):
        try:
            os.remove(full_local_path)
        except OSError:
            pass

    os.rename(temp_path, full_local_path)

    stat = os.stat(full_local_path)
    plaintext_hash = hash_utils.hash_file(full_local_path)

    cur.execute("""
        INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id, encrypted_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (full_local_path, plaintext_hash, stat.st_size, stat.st_mtime, version_id, remote_hash))

    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (full_local_path,))
    for idx, ch in enumerate(remote_chunk_hashes):
        cur.execute("""
            INSERT INTO chunk_signatures (file_path, chunk_index, hash)
            VALUES (?, ?, ?)
        """, (full_local_path, idx, ch))

    conn.commit()
    logger.success("Delta reconstructed: {}", rel_path)
    network_client.ack_sync(device_id, file_id, version_id)


def run_downstream_sync_async(device_id: int):
    """Trigger downstream download sync process in background if not already running."""
    def target():
        if not _downstream_sync_lock.acquire(blocking=False):
            return
        try:
            process_downstream_downloads(device_id)
        except Exception as e:
            logger.error("Download pipeline crash: {}", e)
        finally:
            _downstream_sync_lock.release()

    t = threading.Thread(target=target, name="downstream-sync", daemon=True)
    t.start()
