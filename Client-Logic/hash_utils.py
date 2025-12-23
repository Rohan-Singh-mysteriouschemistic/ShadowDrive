import hashlib

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB

def hash_file(file_path):
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()
