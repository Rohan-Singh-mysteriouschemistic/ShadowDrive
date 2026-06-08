"""
diff_engine.py — High-Performance Metadata Shadow Database Engine
Tracks incremental differentials and logs state changes into local shadow DB entries.
"""

import os
import sqlite3
from datetime import datetime
from hash_utils import hash_file
import config

# Fallback checking logic ensures matching targets across scripts
config.DB_PATH = getattr(config, 'DB_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shadow.db"))
config.WATCH_DIR = getattr(config, 'WATCH_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "watch_folder"))

def ensure_db():
    """Initializes local state layout schemas inside shadow.db context."""
    conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_path     TEXT PRIMARY KEY,
            hash          TEXT NOT NULL,
            size          INTEGER NOT NULL,
            last_modified REAL NOT NULL
        )
    """)
    try:
        cur.execute("ALTER TABLE files ADD COLUMN version_id INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE files ADD COLUMN encrypted_hash TEXT")
    except sqlite3.OperationalError:
        pass

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
    try:
        cur.execute("ALTER TABLE events ADD COLUMN version_id INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunk_signatures (
            file_path   TEXT,
            chunk_index INTEGER,
            hash        TEXT NOT NULL,
            PRIMARY KEY (file_path, chunk_index)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chunk_signatures_hash ON chunk_signatures (hash)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_chunk_uploads (
            file_path      TEXT,
            chunk_index    INTEGER,
            nonce          BLOB NOT NULL,
            plaintext_hash TEXT,
            PRIMARY KEY (file_path, chunk_index)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS local_chunk_nonces (
            file_path      TEXT,
            chunk_index    INTEGER,
            nonce          BLOB NOT NULL,
            plaintext_hash TEXT,
            PRIMARY KEY (file_path, chunk_index)
        )
    """)

    conn.commit()
    conn.close()

def _log_event(cur, event_type, file_path, file_hash=None, version_id=0):
    """Stages outbound transactional changes into temporary action tables."""
    timestamp = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO events (event_type, file_path, hash, timestamp, version_id)
        VALUES (?, ?, ?, ?, ?)
    """, (event_type, file_path, file_hash, timestamp, version_id))

def _delete_file(cur, path):
    """Clears tracking maps out of local shadow DB indices."""
    cur.execute("DELETE FROM files WHERE file_path = ?", (path,))
    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (path,))

def update_chunk_signatures(cur, file_path):
    """Generates and updates chunk hashes in the chunk_signatures table."""
    from hash_utils import chunk_and_hash_file
    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (file_path,))
    chunk_hashes = chunk_and_hash_file(file_path)
    for idx, h in enumerate(chunk_hashes):
        cur.execute("""
            INSERT INTO chunk_signatures (file_path, chunk_index, hash)
            VALUES (?, ?, ?)
        """, (file_path, idx, h))

def process_single_file(path, event_type):
    """Processes discrete event mutations targeted by OS folder hooks."""
    from sync_engine import is_local_mutation_active
    
    # CRITICAL: If Week 6 download worker generated this change, ignore it
    if is_local_mutation_active():
        return

    ensure_db()
    conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
    cur  = conn.cursor()

    if event_type == "deleted":
        print(f"[DELETED]  {os.path.basename(path)}")
        _log_event(cur, "deleted", path)
        _delete_file(cur, path)
    else:
        try:
            if not os.path.exists(path):
                conn.close()
                return
            stat      = os.stat(path)
            file_hash = hash_file(path)

            if not file_hash: 
                conn.close()
                return

            cur.execute("SELECT hash, version_id FROM files WHERE file_path = ?", (path,))
            row = cur.fetchone()
            
            db_hash = row[0] if row else None
            version_id = row[1] if row else 0

            if row is None:
                print(f"[NEW]      {os.path.basename(path)}")
                _log_event(cur, "new", path, file_hash, version_id)
            elif db_hash != file_hash:
                print(f"[MODIFIED] {os.path.basename(path)}")
                _log_event(cur, "modified", path, file_hash, version_id)
            else:
                conn.close()
                return

            cur.execute("""
                INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id)
                VALUES (?, ?, ?, ?, ?)
            """, (path, file_hash, stat.st_size, stat.st_mtime, version_id))
            
            update_chunk_signatures(cur, path)
            
        except OSError:
            conn.close()
            return

    conn.commit()
    conn.close()

def run_full_scan():
    """Bootstrap scanner that catches changes made while agent daemon was completely dark."""
    ensure_db()
    
    from sync_engine import is_local_mutation_active
    if is_local_mutation_active():
        return

    if not os.path.exists(config.WATCH_DIR):
        os.makedirs(config.WATCH_DIR)

    conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
    cur  = conn.cursor()

    cur.execute("SELECT file_path, hash, version_id FROM files")
    db_records = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

    current_paths = set()

    for root, _, files in os.walk(config.WATCH_DIR):
        for file in files:
            full_path = os.path.join(root, file)
            current_paths.add(full_path)
            
            try:
                stat = os.stat(full_path)
                h = hash_file(full_path)
                if not h:
                    continue

                if full_path not in db_records:
                    print(f"[BOOTSTRAP FIND] New entry -> {file}")
                    _log_event(cur, "new", full_path, h, 0)
                    cur.execute("INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id) VALUES (?, ?, ?, ?, ?)", 
                                (full_path, h, stat.st_size, stat.st_mtime, 0))
                    update_chunk_signatures(cur, full_path)
                elif db_records[full_path][0] != h:
                    print(f"[BOOTSTRAP FIND] Modified entry -> {file}")
                    _log_event(cur, "modified", full_path, h, db_records[full_path][1])
                    cur.execute("INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id) VALUES (?, ?, ?, ?, ?)", 
                                (full_path, h, stat.st_size, stat.st_mtime, db_records[full_path][1]))
                    update_chunk_signatures(cur, full_path)
            except OSError:
                continue

    for tracked_path in db_records:
        if tracked_path not in current_paths:
            print(f"[BOOTSTRAP FIND] Vanished entry -> {os.path.basename(tracked_path)}")
            _log_event(cur, "deleted", tracked_path, None, db_records[tracked_path][1])
            cur.execute("DELETE FROM files WHERE file_path = ?", (tracked_path,))
            cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (tracked_path,))

    conn.commit()
    conn.close()