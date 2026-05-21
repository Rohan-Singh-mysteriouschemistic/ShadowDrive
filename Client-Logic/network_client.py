"""
network_client.py — HTTP transport layer for ShadowDrive++ client (Week 6)
Handles bidirectional payload transfers with Shabd's backend API.
"""

import os
import logging
import requests
import config

logger = logging.getLogger(__name__)

# Reused connection pool session for TCP keep-alive
_session = requests.Session()

def health_check() -> bool:
    """Ping the server's /health endpoint to check network availability."""
    try:
        resp = _session.get(f"{config.SERVER_BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.RequestException as e:
        logger.warning("Health check failed: %s", e)
        return False

def announce_metadata(relative_path: str, file_hash: str, event_type: str, base_version_id: int = None, client_modified_at: str = None) -> tuple[bool, dict]:
    """Announce local file mutations to the server metadata repository."""
    try:
        payload = {
            "path": relative_path,
            "hash": file_hash,
            "event": event_type
        }
        if base_version_id is not None:
            payload["base_version_id"] = base_version_id
        if client_modified_at is not None:
            payload["client_modified_at"] = client_modified_at
        resp = _session.post(
            f"{config.SERVER_BASE_URL}/sync/announce",
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Metadata announcement failed for %s: %s", relative_path, e)
        return False, {}

def upload_file(relative_path: str, local_path: str) -> tuple[bool, dict]:
    """Single-shot upload handler optimized for files smaller than chunk threshold."""
    try:
        if not os.path.exists(local_path):
            return False, {"error": "Local file does not exist", "retriable": False}
        with open(local_path, "rb") as f:
            files = {"file": (os.path.basename(local_path), f, "application/octet-stream")}
            data = {"file_path": relative_path}
            resp = _session.post(
                f"{config.SERVER_BASE_URL}/sync/upload",
                files=files,
                data=data,
                timeout=120
            )
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.HTTPError as e:
        logger.error("Single-shot upload HTTP error for %s: %s", relative_path, e)
        status_code = e.response.status_code if e.response is not None else 500
        # Retry on 5xx (server error) or 429 (Too Many Requests), but not on 4xx (client errors)
        retriable = (status_code >= 500 or status_code == 429)
        return False, {"error": str(e), "retriable": retriable, "status_code": status_code}
    except (requests.RequestException, OSError) as e:
        logger.error("Single-shot upload failed for %s: %s", relative_path, e)
        # Transient network issues/timeouts are retriable; local OSErrors are usually not
        retriable = isinstance(e, requests.RequestException)
        return False, {"error": str(e), "retriable": retriable}

def upload_chunk(local_path: str, offset: int, chunk_size: int, chunk_index: int, total_chunks: int, file_hash: str, version_id: int) -> tuple[bool, dict]:
    """Reads and transmits a slice of a multi-part file transaction."""
    try:
        with open(local_path, "rb") as f:
            f.seek(offset)
            chunk_data = f.read(chunk_size)

        files = {"chunk": ("chunk_data", chunk_data)}
        data = {
            "version_id": str(version_id),
            "chunk_index": str(chunk_index),
            "total_chunks": str(total_chunks),
            "file_hash": file_hash,
        }

        resp = _session.post(
            f"{config.SERVER_BASE_URL}/sync/upload_chunk",
            files=files,
            data=data,
            timeout=120
        )
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.HTTPError as e:
        logger.error("Chunk upload HTTP error (index=%d/%d): %s", chunk_index, total_chunks, e)
        status_code = e.response.status_code if e.response is not None else 500
        retriable = (status_code >= 500 or status_code == 429)
        return False, {"error": str(e), "retriable": retriable, "status_code": status_code}
    except (requests.RequestException, OSError) as e:
        logger.error("Chunk upload failed (index=%d/%d): %s", chunk_index, total_chunks, e)
        retriable = isinstance(e, requests.RequestException)
        return False, {"error": str(e), "retriable": retriable}

# ─── WEEK 6 DOWNLOAD PIPELINE IMPLEMENTATION ─────────────────────────────────

def get_metadata_diff(device_id: int) -> tuple[bool, dict]:
    """GET /sync/metadata/diff?device_id=<id> — Fetch diff payload for two-way sync."""
    try:
        params = {"device_id": str(device_id)}
        resp = _session.get(f"{config.SERVER_BASE_URL}/sync/metadata/diff", params=params, timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch metadata diff: %s", e)
        return False, {}

def download_file(storage_path: str) -> tuple[bool, bytes]:
    """Downloads a complete single-shot file directly from the remote backend."""
    try:
        params = {"storage_path": storage_path}
        resp = _session.get(f"{config.SERVER_BASE_URL}/sync/download", params=params, timeout=60)
        resp.raise_for_status()
        return True, resp.content
    except requests.RequestException as e:
        logger.error("Failed downloading file %s: %s", storage_path, e)
        return False, b""

def ack_sync(device_id: int, file_id: int, version_id: int) -> bool:
    """Acknowledge successful sync of a file to update server mapping."""
    try:
        data = {
            "device_id": str(device_id),
            "file_id": str(file_id),
            "version_id": str(version_id)
        }
        resp = _session.post(f"{config.SERVER_BASE_URL}/sync/ack_sync", data=data, timeout=30)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error("Failed to ack sync for file %d version %d: %s", file_id, version_id, e)
        return False