import hashlib

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


def hash_file(file_path):
    """
    Compute SHA256 hash of a file, reading in 4MB chunks.
    Returns hex digest string, or None if file cannot be read.
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