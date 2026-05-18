"""
network_client.py — HTTP transport layer for ShadowDrive++ client (Week 5)

This module handles all HTTP communication between Rohan's sync engine
and Shabd's FastAPI server.  The sync_engine.py and upload worker call
these functions — they never use `requests` directly.

Design decisions:
    - requests.Session() is reused for connection pooling (TCP keep-alive).
    - Every call returns a (success: bool, data: dict) tuple so the caller
      can decide how to handle failures without try/except boilerplate.
    - Timeouts are generous (30s for metadata, 120s for uploads) to
      accommodate large files over slow connections.
"""

import os
import logging
import requests

import config

logger = logging.getLogger(__name__)

# ─── Shared Session ──────────────────────────────────────────────────────────
_session = requests.Session()


def health_check() -> bool:
    """Ping the server's /health endpoint.

    Returns True if the server is reachable, False otherwise.
    Called at the start of every sync cycle.
    """
    try:
        resp = _session.get(
            f"{config.SERVER_BASE_URL}/health",
            timeout=5
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        logger.warning("Health check failed: %s", e)
        return False


def announce_metadata(path: str, file_hash: str | None, event: str) -> tuple[bool, dict]:
    """POST /sync/announce — tell the server about a file change.

    Args:
        path:      Relative file path (e.g. "docs/readme.txt").
        file_hash: SHA-256 hex digest, or None for deletions.
        event:     One of "new", "modified", "deleted".

    Returns:
        (True, response_json) on success, (False, {}) on failure.
    """
    payload = {"path": path, "hash": file_hash, "event": event}
    try:
        resp = _session.post(
            f"{config.SERVER_BASE_URL}/sync/announce",
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("announce_metadata failed for '%s': %s", path, e)
        return False, {}


def upload_file(remote_path: str, local_path: str) -> tuple[bool, dict]:
    """POST /sync/upload — single-shot upload for small files.

    Args:
        remote_path: The relative path the server expects (from announce).
        local_path:  Absolute path to the local file on Windows.

    Returns:
        (True, response_json) on success, (False, {}) on failure.
    """
    try:
        with open(local_path, "rb") as f:
            files = {"file": (remote_path, f)}
            resp = _session.post(
                f"{config.SERVER_BASE_URL}/sync/upload",
                files=files,
                timeout=120
            )
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("upload_file failed for '%s': %s", remote_path, e)
        return False, {}
    except OSError as e:
        logger.error("Cannot read local file '%s': %s", local_path, e)
        return False, {}


def upload_chunk(
    local_path: str,
    version_id: int,
    chunk_index: int,
    total_chunks: int,
    file_hash: str,
    offset: int,
    chunk_size: int
) -> tuple[bool, dict]:
    """POST /sync/upload_chunk — upload a single chunk of a large file.

    Reads `chunk_size` bytes from `local_path` starting at `offset` and
    sends them to the server along with chunk metadata as form fields.

    Args:
        local_path:    Absolute path to the local file.
        version_id:    Server-assigned version ID from /sync/announce.
        chunk_index:   0-based index of this chunk.
        total_chunks:  Total number of chunks for this file.
        file_hash:     SHA-256 hex digest of the entire file.
        offset:        Byte offset to start reading from.
        chunk_size:    Number of bytes to read for this chunk.

    Returns:
        (True, response_json) on success, (False, {}) on failure.
    """
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
    except requests.RequestException as e:
        logger.error(
            "upload_chunk failed (version=%d, chunk=%d/%d): %s",
            version_id, chunk_index, total_chunks, e
        )
        return False, {}
    except OSError as e:
        logger.error("Cannot read local file '%s': %s", local_path, e)
        return False, {}


def get_server_metadata() -> tuple[bool, list]:
    """GET /sync/metadata — fetch the server's file manifest.

    Returns:
        (True, list_of_file_versions) on success, (False, []) on failure.
    """
    try:
        resp = _session.get(
            f"{config.SERVER_BASE_URL}/sync/metadata",
            timeout=30
        )
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("get_server_metadata failed: %s", e)
        return False, []
