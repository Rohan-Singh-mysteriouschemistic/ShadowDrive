import hashlib

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB

# The SHA-256 hash of zero bytes.  Produced by hashlib.sha256(b"").hexdigest().
# We store this as a constant so both the client and server can recognise
# 0-byte files without any special-case branching in the hashing logic.
EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def hash_file(file_path):
    """
    Compute SHA256 hash of a file, reading in 4MB chunks.
    Returns hex digest string, or None if file cannot be read.

    Week 4 Hardening (Scenario A):
        - A 0-byte file (e.g., `touch empty.txt`) is perfectly valid.
          hashlib.sha256 with zero update() calls produces a well-known
          constant hash (EMPTY_FILE_SHA256 above).
        - The old code already handled this correctly—sha256.hexdigest()
          returns the empty hash when no chunks are read—but we now
          make this behaviour explicit and tested.
    """
    sha256 = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    except (IOError, OSError, PermissionError):
        return None