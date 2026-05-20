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

def announce_metadata(relative_path: str, file_hash: str, event_type: str) -> tuple[bool, dict]:
    """Announce local file mutations to the server metadata repository."""
    try:
        payload = {
            "file_path": relative_path,
            "file_hash": file_hash,
            "event_type": event_type
        }
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
            return False, {}
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
    except (requests.RequestException, OSError) as e:
        logger.error("Single-shot upload failed for %s: %s", relative_path, e)
        return False, {}

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
    except (requests.RequestException, OSError) as e:
        logger.error("Chunk upload failed (index=%d/%d): %s", chunk_index, total_chunks, e)
        return False, {}

# ─── WEEK 6 DOWNLOAD PIPELINE IMPLEMENTATION ─────────────────────────────────

def get_server_metadata() -> tuple[bool, list]:
    """GET /sync/metadata — Fetch downstream remote server file manifest."""
    try:
        resp = _session.get(f"{config.SERVER_BASE_URL}/sync/metadata", timeout=30)
        resp.raise_for_status()
        # Returns a structured list of files present on the remote host
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch server metadata manifest: %s", e)
        return False, []

def download_file(relative_path: str) -> tuple[bool, bytes]:
    """Downloads a complete single-shot file directly from the remote backend."""
    try:
        params = {"file_path": relative_path}
        resp = _session.get(f"{config.SERVER_BASE_URL}/sync/download", params=params, timeout=60)
        resp.raise_for_status()
        return True, resp.content
    except requests.RequestException as e:
        logger.error("Failed downloading single-shot file %s: %s", relative_path, e)
        return False, b""

def download_chunk(file_hash: str, chunk_index: int, version_id: int) -> tuple[bool, bytes]:
    """Downloads a designated raw block segment via discrete hash identifiers."""
    try:
        params = {
            "file_hash": file_hash,
            "chunk_index": str(chunk_index),
            "version_id": str(version_id)
        }
        resp = _session.get(f"{config.SERVER_BASE_URL}/sync/download_chunk", params=params, timeout=60)
        resp.raise_for_status()
        return True, resp.content
    except requests.RequestException as e:
        logger.error("Failed downloading chunk %d for hash %s: %s", chunk_index, file_hash, e)
        return False, b""