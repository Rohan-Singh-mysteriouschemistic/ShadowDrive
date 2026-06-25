"""
network_client.py — HTTP transport layer for ShadowDrive++ client (Week 6+)
Handles bidirectional payload transfers with Shabd's backend API.
"""

import json
import os
import sqlite3
import sys
import threading
from typing import Optional

import config
import requests
import resilient_http
from loguru import logger

try:
    import keyring
except ImportError:
    keyring = None


# ─── Secure local key storage helpers ────────────────────────────────────────

def _get_secure_file_setting(key: str) -> Optional[str]:
    filepath = os.path.expanduser("~/.config/shadowdrive/keys")
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath) as f:
            data = json.load(f)
        return data.get(key)
    except Exception as e:
        logger.error("Failed to read secure keys file: {}", e)
        return None


def _save_secure_file_setting(key: str, value: Optional[str]):
    filepath = os.path.expanduser("~/.config/shadowdrive/keys")
    dirpath = os.path.dirname(filepath)
    try:
        os.makedirs(dirpath, exist_ok=True)
        data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath) as f:
                    data = json.load(f)
            except Exception:
                pass

        if value is None:
            data.pop(key, None)
        else:
            data[key] = value

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(filepath, flags, mode)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.chmod(filepath, 0o600)
    except Exception as e:
        logger.error("Failed to write secure keys file: {}", e)


def _get_secure_setting(key: str) -> Optional[str]:
    if keyring is not None:
        try:
            val = keyring.get_password("shadowdrive", key)
            if val is not None:
                return val
        except Exception as e:
            logger.debug("keyring.get_password failed for key '{}': {}", key, e)
    return _get_secure_file_setting(key)


def _save_secure_setting(key: str, value: Optional[str]):
    # Synchronize memory settings cache
    with _settings_cache_lock:
        if value is None:
            _settings_cache.pop(key, None)
        else:
            _settings_cache[key] = value

    saved_in_keyring = False
    if keyring is not None:
        try:
            if value is None:
                try:
                    keyring.delete_password("shadowdrive", key)
                except Exception:
                    pass
            else:
                keyring.set_password("shadowdrive", key, value)
            saved_in_keyring = True
        except Exception as e:
            logger.debug("keyring action failed for key '{}': {}", key, e)

    if not saved_in_keyring:
        _save_secure_file_setting(key, value)


# ─── Settings Database Helpers ───────────────────────────────────────────────

# ─── Settings Cache & Encryption ──────────────────────────────────────────────

_settings_cache = {}
_settings_cache_lock = threading.Lock()
_settings_loaded = False
_refresh_lock = threading.RLock()


def _encrypt_val(key: str, val: str) -> str:
    """Encrypt sensitive values using Windows DPAPI if running on Windows."""
    if key == "encryption_key" and sys.platform == "win32":
        try:
            import win32crypt
            encrypted_bytes = win32crypt.CryptProtectData(val.encode('utf-8'), "ShadowDriveKey", None, None, None, 0)
            return "dpapi:" + encrypted_bytes.hex()
        except Exception as e:
            logger.error("DPAPI encryption failed for '{}': {}", key, e)
            return val
    return val


def _decrypt_val(key: str, val: str) -> str:
    """Decrypt sensitive values using Windows DPAPI if running on Windows."""
    if key in ("encryption_key", "jwt_token"):
        return _get_secure_setting(key)
    if key == "encryption_key" and val and val.startswith("dpapi:"):
        if sys.platform == "win32":
            try:
                import win32crypt
                raw_hex = val[len("dpapi:"):]
                encrypted_bytes = bytes.fromhex(raw_hex)
                desc, decrypted_bytes = win32crypt.CryptUnprotectData(encrypted_bytes, None, None, None, 0)
                return decrypted_bytes.decode('utf-8')
            except Exception as e:
                logger.error("DPAPI decryption failed for '{}': {}", key, e)
                return val
    return val


def _load_settings_cache_if_needed():
    """Helper to populate the settings cache from SQLite."""
    global _settings_loaded
    if not _settings_loaded:
        with _settings_cache_lock:
            if not _settings_loaded:
                # Preload secure settings directly from key storage
                for key in ("jwt_token", "encryption_key", "user_email"):
                    val = _get_secure_setting(key)
                    if val is not None:
                        _settings_cache[key] = val

                if os.path.exists(config.DB_PATH):
                    try:
                        conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
                        cur = conn.cursor()
                        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                        cur.execute("SELECT key, value FROM settings")
                        for k, v in cur.fetchall():
                            v = _decrypt_val(k, v)
                            _settings_cache[k] = v
                        conn.close()
                    except Exception as e:
                        logger.error("Failed to preload settings cache: {}", e)
                _settings_loaded = True


def _get_setting(key: str) -> Optional[str]:
    """Reads a value from the settings cache, preloading if needed."""
    _load_settings_cache_if_needed()
    with _settings_cache_lock:
        return _settings_cache.get(key)


def _save_setting(key: str, value: str):
    """Saves a key/value pair to the cache and the local SQLite settings table."""
    _load_settings_cache_if_needed()

    with _settings_cache_lock:
        _settings_cache[key] = value

    db_value = _encrypt_val(key, value)

    if key in ("encryption_key", "jwt_token"):
        _save_secure_setting(key, value)
        return
    try:
        conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, db_value))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to save setting '{}': {}", key, e)


def _get_token() -> Optional[str]:
    """Reads jwt_token from settings."""
    return _get_setting("jwt_token")


def _save_token(token: str):
    """Saves jwt_token to settings."""
    _save_setting("jwt_token", token)


def _clear_device():
    """Clears the old device_id on login to prevent 403 Forbidden cross-user conflicts."""
    _load_settings_cache_if_needed()
    with _settings_cache_lock:
        _settings_cache.pop("device_id", None)
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM settings WHERE key = 'device_id'")
        conn.commit()
        conn.close()
    except Exception:
        pass


def _request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """Wrapper around requests.Session.request to inject auth headers and handle 401."""
    url = f"{config.SERVER_BASE_URL}{endpoint}"

    token = _get_token()
    headers = kwargs.pop("headers", {})
    if token and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers

    resp = resilient_http.request(method, url, **kwargs)

    if resp.status_code == 401 and endpoint != "/auth/refresh":
        with _refresh_lock:
            # Check if token was already refreshed by another thread
            current_token = _get_token()
            if current_token != token:
                headers["Authorization"] = f"Bearer {current_token}"
                kwargs["headers"] = headers
                return resilient_http.request(method, url, **kwargs)

            # Attempt to refresh the token
            if current_token:
                refresh_headers = {"Authorization": f"Bearer {current_token}"}
                refresh_resp = resilient_http.request(
                    "POST",
                    f"{config.SERVER_BASE_URL}/auth/refresh",
                    headers=refresh_headers
                )
                if refresh_resp.status_code == 200:
                    new_token = refresh_resp.json().get("access_token")
                    if new_token:
                        _save_token(new_token)
                        config.sync_suspended = False
                        headers["Authorization"] = f"Bearer {new_token}"
                        kwargs["headers"] = headers
                        return resilient_http.request(method, url, **kwargs)

        # If refresh fails or no token, suspend sync
        logger.error("[AUTH ERROR] Unauthorized (401) and refresh failed. Sync has been suspended. Please login again.")
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
        # Explicitly use resilient_http to avoid token injection & 401 checks for register
        resp = resilient_http.request("POST",
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
        logger.error("Registration request failed: {}", e)
        return False, f"Network error: {e}"


def login_user(email: str, password: str) -> tuple[bool, str]:
    """Authenticates with the server and saves the token if successful (POST /users/login)."""
    try:
        payload = {"email": email, "password": password}
        resp = resilient_http.request("POST",
            f"{config.SERVER_BASE_URL}/auth/login",
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                _save_token(token)

                # Register device to get a valid device_id from server
                me_resp = resilient_http.request("GET", f"{config.SERVER_BASE_URL}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
                if me_resp.status_code == 200:
                    user_id = me_resp.json().get("id")
                    import hashlib
                    import platform
                    dir_hash = hashlib.md5(config.DB_PATH.encode()).hexdigest()[:6]
                    device_name = f"{platform.node()}-{dir_hash}-client"
                    dev_payload = {"user_id": user_id, "device_name": device_name}
                    dev_resp = resilient_http.request("POST", f"{config.SERVER_BASE_URL}/devices/register", json=dev_payload, timeout=10)
                    if dev_resp.status_code in [200, 201]:
                        device_id = dev_resp.json().get("id")
                        _save_setting("device_id", str(device_id))
                        logger.info("Successfully registered device with server: {}", device_id)
                        logger.info("Successfully registered device with server: {}", device_id)
                    else:
                        logger.error("FAILED to register device: {} {}", dev_resp.status_code, dev_resp.text)
                else:
                    logger.error("FAILED to get /auth/me: {} {}", me_resp.status_code, me_resp.text)

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
        logger.error("Login request failed: {}", e)
        return False, f"Network error: {e}"


# ─── Sync & Storage Actions ──────────────────────────────────────────────────

def health_check() -> bool:
    """Ping the server's /health endpoint to check network availability."""
    try:
        resp = resilient_http.request("GET", f"{config.SERVER_BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.RequestException as e:
        logger.warning("Health check failed: {}", e)
        return False


def send_heartbeat(device_id: int) -> tuple[bool, list]:
    """POST /devices/{device_id}/heartbeat — Send ping and get pending commands."""
    try:
        resp = _request("POST", f"/devices/{device_id}/heartbeat", timeout=10)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.debug("Heartbeat failed: {}", e)
        return False, []

def ack_command(device_id: int, command_id: int) -> bool:
    """POST /devices/{device_id}/command/{command_id}/ack"""
    try:
        resp = _request("POST", f"/devices/{device_id}/command/{command_id}/ack", timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
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
        logger.error("Metadata announcement failed for {}: {}", relative_path, e)
        return False, {}


def upload_file(relative_path: str, local_path: str, data: bytes = None, version_id: int = None) -> tuple[bool, dict]:
    """Single-shot upload handler. If *data* is provided, those bytes are sent
    instead of reading from *local_path* (used for encrypted uploads).
    Pass *version_id* (from /announce) so the server targets the exact version."""
    try:
        extra_fields = {}
        if version_id is not None:
            extra_fields["version_id"] = str(version_id)

        if data is not None:
            import io
            files = {"file": (relative_path, io.BytesIO(data), "application/octet-stream")}
            resp = _request("POST", "/sync/upload", files=files, data=extra_fields, timeout=120)
        else:
            if not os.path.exists(local_path):
                return False, {}
            with open(local_path, "rb") as f:
                files = {"file": (relative_path, f, "application/octet-stream")}
                resp = _request("POST", "/sync/upload", files=files, data=extra_fields, timeout=120)
        resp.raise_for_status()
        return True, resp.json()
    except (requests.RequestException, OSError) as e:
        logger.error("Single-shot upload failed for {}: {}", relative_path, e)
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
        logger.error("Chunk upload failed (index={}/{}): {}", chunk_index, total_chunks, e)
        return False, {}


# ─── WEEK 6 DOWNLOAD PIPELINE IMPLEMENTATION ─────────────────────────────────

def get_upload_status(version_id: int) -> tuple[bool, dict]:
    """GET /sync/upload/status/{version_id} — Fetch which chunks have been received."""
    try:
        resp = _request("GET", f"/sync/upload/status/{version_id}", timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to get upload status for version {}: {}", version_id, e)
        return False, {}


def get_server_metadata() -> tuple[bool, list]:
    """GET /sync/metadata — Fetch downstream remote server file manifest."""
    try:
        resp = _request("GET", "/sync/metadata", timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch server metadata manifest: {}", e)
        return False, []


def get_metadata_diff(device_id: int) -> tuple[bool, dict]:
    """GET /sync/metadata/diff — Fetch diff between server canonical state and device state."""
    try:
        params = {"device_id": device_id}
        resp = _request("GET", "/sync/metadata/diff", params=params, timeout=30)
        if resp.status_code == 403:
            logger.warning("Device ID is forbidden (likely registered to another user). Wiping local device_id.")
            _clear_device()
            return False, {}
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch metadata diff: {}", e)
        return False, {}


def download_file(storage_path: str) -> tuple[bool, bytes]:
    """Downloads a complete single-shot file directly from the remote backend."""
    try:
        params = {"storage_path": storage_path}
        resp = _request("GET", "/sync/download", params=params, timeout=60)
        resp.raise_for_status()
        return True, resp.content
    except requests.RequestException as e:
        logger.error("Failed downloading single-shot file {}: {}", storage_path, e)
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
        logger.error("Failed downloading chunk {} for hash {}: {}", chunk_index, file_hash, e)
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
        logger.error("Failed to ack sync for file_id={} version_id={}: {}", file_id, version_id, e)
        return False, {}
