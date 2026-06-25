"""
config.py — Client configuration for ShadowDrive++ (Week 6 Update)
Handles environment configurations with Pydantic and YAML.
"""

import os

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    url: str = "http://localhost:8000"
    api_key: str = ""

class ClientConfig(BaseModel):
    watch_folder: str = os.path.expanduser("~/ShadowDrive")
    chunk_size_mb: int = 4
    sync_interval_sec: int = 10
    max_retries: int = 5
    compression: str = "none"

class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = ""
    json_format: bool = Field(False, alias="json")

class EncryptionConfig(BaseModel):
    algorithm: str = "AES-256-GCM"
    pbkdf2_iterations: int = 100000

class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    client: ClientConfig = ClientConfig()
    logging: LoggingConfig = LoggingConfig()
    encryption: EncryptionConfig = EncryptionConfig()

def load_config(path: str) -> AppConfig:
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return AppConfig.model_validate(data)
    return AppConfig()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_config_path = os.path.join(BASE_DIR, "shadowdrive.yaml")
app_config = load_config(_config_path)

# ─── Export Existing Module-Level Variables for Compatibility ────────────────
SERVER_BASE_URL = app_config.server.url

# Maintain existing default DB and watch folder fallback logic if not absolute
_watch = app_config.client.watch_folder
if not _watch.startswith("/") and not _watch.startswith("~"):
    WATCH_DIR = os.path.abspath(os.path.join(BASE_DIR, _watch))
else:
    WATCH_DIR = os.path.expanduser(_watch)

DB_PATH = os.path.join(BASE_DIR, "shadow.db")

CHUNK_SIZE = app_config.client.chunk_size_mb * 1024 * 1024
CHUNK_THRESHOLD = CHUNK_SIZE

SYNC_INTERVAL_SECONDS = app_config.client.sync_interval_sec

UPLOAD_MAX_RETRIES = app_config.client.max_retries
RETRY_BACKOFF_SECONDS = 2
RETRY_MAX_BACKOFF_SECONDS = 60

HASH_ALGORITHM = "sha256"

COMPRESSION = app_config.client.compression  # "none" or "zlib"

# ─── Auth State ──────────────────────────────────────────────────────────────
sync_suspended = False
encryption_key = None

def update_user_config(email: str):
    """Dynamically updates database and watcher directory paths to isolate data per user."""
    from loguru import logger
    # Clean email to form a valid file/directory name component
    email_clean = "".join([c if c.isalnum() or c in ".-_" else "_" for c in email])
    
    global WATCH_DIR, DB_PATH
    WATCH_DIR = os.path.expanduser(f"~/ShadowDrive_{email_clean}")
    DB_PATH = os.path.join(BASE_DIR, f"shadow_{email_clean}.db")
    
    os.makedirs(WATCH_DIR, exist_ok=True)
    logger.info("Paths dynamically updated for {}: WATCH_DIR={}, DB_PATH={}", email, WATCH_DIR, DB_PATH)

