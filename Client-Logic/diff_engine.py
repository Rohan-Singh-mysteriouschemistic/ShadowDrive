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
    conn = sqlite3.connect(config.DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_path     TEXT PRIMARY KEY,
            hash          TEXT NOT NULL,
            size          INTEGER NOT NULL,
            last_modified REAL NOT NULL
        )
    """)
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

def _log_event(cur, event_type, file_path, file_hash=None):
    """Stages outbound transactional changes into temporary action tables."""
    timestamp = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO events (event_type, file_path, hash, timestamp)
        VALUES (?, ?, ?, ?)
    """, (event_type, file_path, file_hash, timestamp))

def _delete_file(cur, path):
    """Clears tracking maps out of local shadow DB indices."""
    cur.execute("DELETE FROM files WHERE file_path = ?", (path,))

def process_single_file(path, event_type):
    """Processes discrete event mutations targeted by OS folder hooks."""
    from sync_engine import is_local_mutation_active
    
    # CRITICAL: If Week 6 download worker generated this change, ignore it
    if is_local_mutation_active():
        return

    ensure_db()
    conn = sqlite3.connect(config.DB_PATH)
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

            cur.execute("SELECT hash FROM files WHERE file_path = ?", (path,))
            row = cur.fetchone()

            if row is None:
                print(f"[NEW]      {os.path.basename(path)}")
                _log_event(cur, "new", path, file_hash)
            elif row[0] != file_hash:
                print(f"[MODIFIED] {os.path.basename(path)}")
                _log_event(cur, "modified", path, file_hash)
            else:
                conn.close()
                return

            cur.execute("""
                INSERT OR REPLACE INTO files (file_path, hash, size, last_modified)
                VALUES (?, ?, ?, ?)
            """, (path, file_hash, stat.st_size, stat.st_mtime))
            
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

    conn = sqlite3.connect(config.DB_PATH)
    cur  = conn.cursor()

    cur.execute("SELECT file_path, hash FROM files")
    db_records = {row[0]: row[1] for row in cur.fetchall()}

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
                    _log_event(cur, "new", full_path, h)
                    cur.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?)", 
                                (full_path, h, stat.st_size, stat.st_mtime))
                elif db_records[full_path] != h:
                    print(f"[BOOTSTRAP FIND] Modified entry -> {file}")
                    _log_event(cur, "modified", full_path, h)
                    cur.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?)", 
                                (full_path, h, stat.st_size, stat.st_mtime))
            except OSError:
                continue

    for tracked_path in db_records:
        if tracked_path not in current_paths:
            print(f"[BOOTSTRAP FIND] Vanished entry -> {os.path.basename(tracked_path)}")
            _log_event(cur, "deleted", tracked_path)
            cur.execute("DELETE FROM files WHERE file_path = ?", (tracked_path,))

    conn.commit()
    conn.close()