"""
config.py — Client configuration for ShadowDrive++ (Week 6 Update)
Handles environment configurations with clean professional fallbacks.
"""

import os

# ─── Server Connection ───────────────────────────────────────────────────────
SERVER_BASE_URL = os.getenv("SHADOWDRIVE_SERVER", "http://localhost:8000")

# ─── Watch Directory ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Using unified watch_folder relative path to align across modules
WATCH_DIR = os.getenv("SHADOWDRIVE_WATCH_DIR", os.path.join(BASE_DIR, "watch_folder"))
DB_PATH = os.path.join(BASE_DIR, "shadow.db")

# ─── Chunking Configuration ─────────────────────────────────────────────────
# Split criteria for files processed through upload/download pipelines
CHUNK_SIZE = int(os.getenv("SHADOWDRIVE_CHUNK_SIZE", str(4 * 1024 * 1024)))  # 4 MB
CHUNK_THRESHOLD = CHUNK_SIZE  

# ─── Sync Engine Timing ─────────────────────────────────────────────────────
SYNC_INTERVAL_SECONDS = int(os.getenv("SHADOWDRIVE_SYNC_INTERVAL", "10"))

# ─── Resilience & Failover ──────────────────────────────────────────────────
UPLOAD_MAX_RETRIES = int(os.getenv("SHADOWDRIVE_UPLOAD_RETRIES", "5"))  # Increased to 5 as default for network retries
RETRY_BACKOFF_SECONDS = 2
RETRY_MAX_BACKOFF_SECONDS = 60

# ─── Hashing ─────────────────────────────────────────────────────────────────
HASH_ALGORITHM = "sha256"

# ─── Auth State ──────────────────────────────────────────────────────────────
sync_suspended = False
encryption_key = None
