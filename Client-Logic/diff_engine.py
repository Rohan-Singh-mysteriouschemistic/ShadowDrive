import os
import sqlite3
from hash_utils import hash_file

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "shadow.db")
WATCH_FOLDER = os.path.join(BASE_DIR, "watch_folder")

def scan_files():
    snapshot = {}

    for root, _, files in os.walk(WATCH_FOLDER):
        for name in files:
            path = os.path.join(root, name)
            stat = os.stat(path)

            snapshot[path] = {
                "hash": hash_file(path),
                "size": stat.st_size,
                "mtime": stat.st_mtime
            }

    return snapshot


def load_db_state(cursor):
    cursor.execute("SELECT file_path, hash, size, last_modified FROM files")
    rows = cursor.fetchall()

    db_state = {}
    for path, h, size, mtime in rows:
        db_state[path] = {"hash": h,"size": size,"mtime": mtime}

    return db_state


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    current = scan_files()
    previous = load_db_state(cur)

    current_paths = set(current.keys())
    previous_paths = set(previous.keys())

    # NEW files
    for path in current_paths - previous_paths:
        print(f"NEW: {os.path.basename(path)}")

    # DELETED files
    for path in previous_paths - current_paths:
        print(f"DELETED: {os.path.basename(path)}")

    # MODIFIED files
    for path in current_paths & previous_paths:
        if current[path]["hash"] != previous[path]["hash"]:
            print(f"MODIFIED: {os.path.basename(path)}")

    # Update shadow state (truth update)
    cur.execute("DELETE FROM files")

    for path, data in current.items():
        cur.execute("""INSERT INTO files (file_path, hash, size, last_modified)VALUES (?, ?, ?, ?)""", (path, data["hash"], data["size"], data["mtime"]))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
