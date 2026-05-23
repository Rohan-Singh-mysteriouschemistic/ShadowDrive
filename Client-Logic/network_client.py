"""
network_client.py — HTTP transport layer for ShadowDrive++ client (Week 6+)
Handles bidirectional payload transfers with Shabd's backend API.
"""

import os
import logging
import sqlite3
import requests
import config

logger = logging.getLogger(__name__)

# Reused connection pool session for TCP keep-alive
_session = requests.Session()


# ─── Settings Database Helpers ───────────────────────────────────────────────

def _get_setting(key: str) -> str | None:
    """Reads a value from the settings table in SQLite shadow.db."""
    if not os.path.exists(config.DB_PATH):
        return None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception as e:
        logger.error("Failed to read setting '%s': %s", key, e)
    return None


def _save_setting(key: str, value: str):
    """Saves a key/value pair to the settings table in SQLite shadow.db."""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to save setting '%s': %s", key, e)


def _get_token() -> str | None:
    """Reads jwt_token from settings."""
    return _get_setting("jwt_token")


def _save_token(token: str):
    """Saves jwt_token to settings."""
    _save_setting("jwt_token", token)


def _request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """Wrapper around requests.Session.request to inject auth headers and handle 401."""
    url = f"{config.SERVER_BASE_URL}{endpoint}"
    
    token = _get_token()
    if token:
        headers = kwargs.get("headers", {})
        if "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers

    resp = _session.request(method, url, **kwargs)

    if resp.status_code == 401:
        print("[AUTH ERROR] Unauthorized (401). Sync has been suspended. Please login again.")
        config.sync_suspended = True

    return resp


# ─── User Management / CLI Auth API ──────────────────────────────────────────

def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    """Registers a new user on the server (POST /users/register)."""
    try:
        payload = {
            "username": username,
            "email": email,
            "password": password
        }
        # Explicitly use _session to avoid token injection & 401 checks for register
        resp = _session.post(
            f"{config.SERVER_BASE_URL}/users/register",
            json=payload,
            timeout=30
        )
        if resp.status_code == 201:
            return True, "Registration successful. You can now login."
        else:
            try:
                detail = resp.json().get("detail", "Registration failed.")
            except ValueError:
                detail = resp.text or "Registration failed."
            return False, f"Registration failed: {detail}"
    except requests.RequestException as e:
        logger.error("Registration request failed: %s", e)
        return False, f"Network error: {e}"


def login_user(email: str, password: str) -> tuple[bool, str]:
    """Authenticates with the server and saves the token if successful (POST /users/login)."""
    try:
        payload = {"email": email, "password": password}
        # Explicitly use _session to avoid token injection & 401 checks for login
        resp = _session.post(
            f"{config.SERVER_BASE_URL}/users/login",
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                _save_token(token)
                config.sync_suspended = False
                return True, "Login successful."
            else:
                return False, "Token missing from server response."
        else:
            try:
                detail = resp.json().get("detail", "Invalid email or password.")
            except ValueError:
                detail = resp.text or "Invalid email or password."
            return False, f"Login failed: {detail}"
    except requests.RequestException as e:
        logger.error("Login request failed: %s", e)
        return False, f"Network error: {e}"


# ─── Sync & Storage Actions ──────────────────────────────────────────────────

def health_check() -> bool:
    """Ping the server's /health endpoint to check network availability."""
    try:
        resp = _session.get(f"{config.SERVER_BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.RequestException as e:
        logger.warning("Health check failed: %s", e)
        return False


def announce_metadata(relative_path: str, file_hash: str, event_type: str,
                      base_version_id: int = None, client_modified_at: str = None,
                      chunk_hashes: list = None) -> tuple[bool, dict]:
    """Announce local file mutations to the server metadata repository.

    The server schema expects fields: path, hash, event, base_version_id,
    client_modified_at, chunk_hashes.
    """
    try:
        payload = {
            "path": relative_path,
            "hash": file_hash,
            "event": event_type,
        }
        if base_version_id is not None and base_version_id != 0:
            payload["base_version_id"] = base_version_id
        if client_modified_at is not None:
            payload["client_modified_at"] = client_modified_at
        if chunk_hashes is not None:
            payload["chunk_hashes"] = chunk_hashes

        resp = _request("POST", "/sync/announce", json=payload, timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Metadata announcement failed for %s: %s", relative_path, e)
        return False, {}


def upload_file(relative_path: str, local_path: str, data: bytes = None) -> tuple[bool, dict]:
    """Single-shot upload handler. If *data* is provided, those bytes are sent
    instead of reading from *local_path* (used for encrypted uploads)."""
    try:
        if data is not None:
            import io
            files = {"file": (relative_path, io.BytesIO(data), "application/octet-stream")}
            resp = _request("POST", "/sync/upload", files=files, timeout=120)
        else:
            if not os.path.exists(local_path):
                return False, {}
            with open(local_path, "rb") as f:
                files = {"file": (relative_path, f, "application/octet-stream")}
                resp = _request("POST", "/sync/upload", files=files, timeout=120)
        resp.raise_for_status()
        return True, resp.json()
    except (requests.RequestException, OSError) as e:
        logger.error("Single-shot upload failed for %s: %s", relative_path, e)
        return False, {}


def upload_chunk(local_path: str, offset: int, chunk_size: int, chunk_index: int,
                 total_chunks: int, file_hash: str, version_id: int,
                 data: bytes = None) -> tuple[bool, dict]:
    """Reads and transmits a slice of a multi-part file transaction.
    If *data* is provided, those bytes are sent instead of reading from disk."""
    try:
        if data is not None:
            chunk_data = data
        else:
            with open(local_path, "rb") as f:
                f.seek(offset)
                chunk_data = f.read(chunk_size)

        files = {"chunk": ("chunk_data", chunk_data)}
        form_data = {
            "version_id": str(version_id),
            "chunk_index": str(chunk_index),
            "total_chunks": str(total_chunks),
            "file_hash": file_hash,
        }

        resp = _request("POST", "/sync/upload_chunk", files=files, data=form_data, timeout=120)
        resp.raise_for_status()
        return True, resp.json()
    except (requests.RequestException, OSError) as e:
        logger.error("Chunk upload failed (index=%d/%d): %s", chunk_index, total_chunks, e)
        return False, {}


# ─── WEEK 6 DOWNLOAD PIPELINE IMPLEMENTATION ─────────────────────────────────

def get_server_metadata() -> tuple[bool, list]:
    """GET /sync/metadata — Fetch downstream remote server file manifest."""
    try:
        resp = _request("GET", "/sync/metadata", timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch server metadata manifest: %s", e)
        return False, []


def get_metadata_diff(device_id: int) -> tuple[bool, dict]:
    """GET /sync/metadata/diff — Fetch diff between server canonical state and device state."""
    try:
        params = {"device_id": device_id}
        resp = _request("GET", "/sync/metadata/diff", params=params, timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch metadata diff: %s", e)
        return False, {}


def download_file(storage_path: str) -> tuple[bool, bytes]:
    """Downloads a complete single-shot file directly from the remote backend."""
    try:
        params = {"storage_path": storage_path}
        resp = _request("GET", "/sync/download", params=params, timeout=60)
        resp.raise_for_status()
        return True, resp.content
    except requests.RequestException as e:
        logger.error("Failed downloading single-shot file %s: %s", storage_path, e)
        return False, b""


def download_chunk(file_hash: str, chunk_index: int, version_id: int) -> tuple[bool, bytes]:
    """Downloads a designated raw block segment via discrete hash identifiers."""
    try:
        params = {
            "file_hash": file_hash,
            "chunk_index": str(chunk_index),
            "version_id": str(version_id)
        }
        resp = _request("GET", "/sync/download_chunk", params=params, timeout=60)
        resp.raise_for_status()
        return True, resp.content
    except requests.RequestException as e:
        logger.error("Failed downloading chunk %d for hash %s: %s", chunk_index, file_hash, e)
        return False, b""


def ack_sync(device_id: int, file_id: int, version_id: int) -> tuple[bool, dict]:
    """POST /sync/ack_sync — Acknowledge that a file version has been synced to this device."""
    try:
        data = {
            "device_id": str(device_id),
            "file_id": str(file_id),
            "version_id": str(version_id)
        }
        resp = _request("POST", "/sync/ack_sync", data=data, timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to ack sync for file_id=%d version_id=%d: %s", file_id, version_id, e)
        return False, {}