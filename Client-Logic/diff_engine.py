import os
import sqlite3
from datetime import datetime
from hash_utils import hash_file

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(BASE_DIR, "shadow.db")
WATCH_FOLDER = os.path.join(BASE_DIR, "watch_folder")


# ─── DB INIT ──────────────────────────────────────────────────────────────────

def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # files table remains the same
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_path     TEXT PRIMARY KEY,
            hash          TEXT NOT NULL,
            size          INTEGER NOT NULL,
            last_modified REAL NOT NULL
        )
    """)
    # UPDATED: Added 'hash' and 'is_synced' columns
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            file_path  TEXT NOT NULL,
            hash       TEXT, 
            is_synced  INTEGER DEFAULT 0,
            timestamp  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _log_event(cur, event_type, file_path, file_hash=None):
    """Write a change event with its hash and sync status."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO events (event_type, file_path, hash, is_synced, timestamp) VALUES (?, ?, ?, 0, ?)",
        (event_type, file_path, file_hash, timestamp)
    )


def _upsert_file(cur, path, data):
    """
    Insert a new file record, or update it if file_path already exists.
    Never touches other rows — no DELETE FROM needed.
    """
    cur.execute("""
        INSERT INTO files (file_path, hash, size, last_modified)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            hash          = excluded.hash,
            size          = excluded.size,
            last_modified = excluded.last_modified
    """, (path, data["hash"], data["size"], data["mtime"]))


def _delete_file(cur, path):
    """Remove a single file record from the shadow DB."""
    cur.execute("DELETE FROM files WHERE file_path = ?", (path,))


def _load_db_state(cur):
    """Return entire shadow DB as a dict keyed by file_path."""
    cur.execute("SELECT file_path, hash, size, last_modified FROM files")
    return {
        path: {"hash": h, "size": size, "mtime": mtime}
        for path, h, size, mtime in cur.fetchall()
    }


def _scan_watch_folder():
    """Walk watch_folder and return current filesystem state as a dict."""
    snapshot = {}

    for root, _, files in os.walk(WATCH_FOLDER):
        for name in files:
            path = os.path.join(root, name)
            try:
                stat      = os.stat(path)
                file_hash = hash_file(path)
                if file_hash:                       # None means unreadable — skip
                    snapshot[path] = {
                        "hash" : file_hash,
                        "size" : stat.st_size,
                        "mtime": stat.st_mtime,
                    }
            except (IOError, OSError):
                continue                            # File disappeared mid-scan

    return snapshot


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def run_full_scan():
    """
    Compare entire watch_folder against shadow DB.
    Used on startup to catch changes that happened while the watcher was off.
    Returns {"new": [...], "modified": [...], "deleted": [...]}.
    """
    ensure_db()

    conn    = sqlite3.connect(DB_PATH)
    cur     = conn.cursor()
    changes = {"new": [], "modified": [], "deleted": []}

    current  = _scan_watch_folder()
    previous = _load_db_state(cur)

    current_paths  = set(current.keys())
    previous_paths = set(previous.keys())

    for path in current_paths - previous_paths:
        print(f"[NEW]      {os.path.basename(path)}")
        _log_event(cur, "new", path, current[path]["hash"])
        _upsert_file(cur, path, current[path])
        changes["new"].append(path)

    for path in previous_paths - current_paths:
        print(f"[DELETED]  {os.path.basename(path)}")
        _log_event(cur, "deleted", path)
        _delete_file(cur, path)
        changes["deleted"].append(path)

    for path in current_paths & previous_paths:
        if current[path]["hash"] != previous[path]["hash"]:
            print(f"[MODIFIED] {os.path.basename(path)}")
            _log_event(cur, "modified", path, current[path]["hash"])
            _upsert_file(cur, path, current[path])
            changes["modified"].append(path)

    conn.commit()
    conn.close()

    total = sum(len(v) for v in changes.values())
    print(f"\nFull scan done — {total} change(s) detected.")
    return changes


def process_single_file(path, event_type):
    """
    Handle one file event fired by the watcher.
    Updates only the affected row — no full scan.

    event_type: "created" | "modified" | "deleted"
    """
    ensure_db()

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    if event_type == "deleted":
        print(f"[DELETED]  {os.path.basename(path)}")
        _log_event(cur, "deleted", path)
        _delete_file(cur, path)

    else:  # "created" or "modified" — both need hash + stat
        try:
            stat      = os.stat(path)
            file_hash = hash_file(path)

            if not file_hash:           # Unreadable (locked, etc.) — skip
                conn.close()
                return

            data = {
                "hash" : file_hash,
                "size" : stat.st_size,
                "mtime": stat.st_mtime,
            }

            # Check if it already exists in DB to label correctly
            cur.execute("SELECT hash FROM files WHERE file_path = ?", (path,))
            row = cur.fetchone()

            if row is None:
                print(f"[NEW]      {os.path.basename(path)}")
                _log_event(cur, "new", path, current[path]["hash"])
            elif row[0] != file_hash:
                print(f"[MODIFIED] {os.path.basename(path)}")
                _log_event(cur, "modified", path, current[path]["hash"])
            else:
                # Hash unchanged (e.g. metadata-only touch) — nothing to do
                conn.close()
                return

            _upsert_file(cur, path, data)

        except (IOError, OSError):
            conn.close()
            return

    conn.commit()
    conn.close()


if __name__ == "__main__":
    run_full_scan()