"""
hash_utils.py — Cryptographic Hash Generation Tools
Handles chunk validation and empty data boundary rules.
"""

import hashlib

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB

# Standard zero bytes SHA-256 token matching constraints
EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

def hash_file(file_path):
    """
    Compute SHA256 hash of a file, reading in 4MB chunks.
    Returns hex digest string, or None if file cannot be read.

    Week 4 Hardening (Scenario A):
        - A 0-byte file (e.g., `touch empty.txt`) is perfectly valid.
          hashlib.sha256 with zero update() calls produces a well-known
          constant hash (EMPTY_FILE_SHA256 above).
    """
    sha256 = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            while True:
                data = f.read(CHUNK_SIZE)
                if not data:
                    break
                sha256.update(data)
        return sha256.hexdigest()
    except OSError:
        return None