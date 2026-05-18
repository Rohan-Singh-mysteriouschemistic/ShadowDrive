"""
config.py — Client configuration for ShadowDrive++ (Week 5)

All tuneable knobs for Rohan's sync client live here.
Environment variables override defaults for deployment flexibility.
"""

import os

# ─── Server Connection ───────────────────────────────────────────────────────
SERVER_BASE_URL = os.getenv("SHADOWDRIVE_SERVER", "http://localhost:8000")

# ─── Watch Directory ─────────────────────────────────────────────────────────
# The folder on the local machine that the sync engine monitors.
# Default: a "ShadowDrive" folder on the user's Desktop.
WATCH_DIR = os.getenv(
    "SHADOWDRIVE_WATCH_DIR",
    os.path.join(os.path.expanduser("~"), "Desktop", "ShadowDrive")
)

# ─── Chunking Configuration ─────────────────────────────────────────────────
# Files larger than CHUNK_THRESHOLD bytes will be split into CHUNK_SIZE-byte
# pieces and uploaded via /sync/upload_chunk.
# Files smaller than CHUNK_THRESHOLD use the single-shot /sync/upload endpoint.
CHUNK_SIZE = int(os.getenv("SHADOWDRIVE_CHUNK_SIZE", str(4 * 1024 * 1024)))  # 4 MB
CHUNK_THRESHOLD = CHUNK_SIZE  # If file >= this size, use chunked upload

# ─── Sync Engine Timing ─────────────────────────────────────────────────────
SYNC_INTERVAL_SECONDS = int(os.getenv("SHADOWDRIVE_SYNC_INTERVAL", "10"))

# ─── Upload Worker ───────────────────────────────────────────────────────────
# Number of retry attempts for a failed chunk upload before giving up.
UPLOAD_MAX_RETRIES = int(os.getenv("SHADOWDRIVE_UPLOAD_RETRIES", "3"))
# Seconds to wait between retries (linear backoff).
UPLOAD_RETRY_DELAY = int(os.getenv("SHADOWDRIVE_RETRY_DELAY", "2"))

# ─── Hashing ─────────────────────────────────────────────────────────────────
HASH_ALGORITHM = "sha256"
