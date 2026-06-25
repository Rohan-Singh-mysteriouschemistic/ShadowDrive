"""
diff_engine.py — High-Performance Metadata Shadow Database Engine
Tracks incremental differentials and logs state changes into local shadow DB entries.
"""

import os
import sqlite3
import time
from datetime import datetime

import config
from hash_utils import compute_file_and_chunk_hashes
from loguru import logger

# Fallback checking logic ensures matching targets across scripts
config.DB_PATH = getattr(config, 'DB_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shadow.db"))
config.WATCH_DIR = getattr(config, 'WATCH_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "watch_folder"))


def get_db_connection(db_path=None, timeout=30.0) -> sqlite3.Connection:
    """Helper to return a thread-safe SQLite connection configured for WAL mode."""
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path, timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def ensure_db():
    """Initializes local state layout schemas inside shadow.db context."""
    conn = get_db_connection()
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

    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_is_synced ON events (is_synced)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files (hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_file_path ON events (file_path, is_synced)")

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

    # Nudge the sync loop to upload immediately
    try:
        import event_listener
        event_listener.sync_nudge.set()
    except Exception:
        pass


def _delete_file(cur, path):
    """Clears tracking maps out of local shadow DB indices."""
    cur.execute("DELETE FROM files WHERE file_path = ?", (path,))
    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (path,))


def update_chunk_signatures(cur, file_path, chunk_hashes=None):
    """Generates and updates chunk hashes in the chunk_signatures table."""
    cur.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (file_path,))
    if chunk_hashes is None:
        from hash_utils import chunk_and_hash_file
        chunk_hashes = chunk_and_hash_file(file_path)
    for idx, h in enumerate(chunk_hashes):
        cur.execute("""
            INSERT INTO chunk_signatures (file_path, chunk_index, hash)
            VALUES (?, ?, ?)
        """, (file_path, idx, h))


def process_single_file(path, event_type):
    """Processes discrete event mutations targeted by OS folder hooks."""
    from state import is_local_mutation_active

    # CRITICAL: If download worker generated this change, ignore it
    if is_local_mutation_active():
        return

    ensure_db()
    conn = get_db_connection()
    cur  = conn.cursor()

    normalized_path = os.path.normpath(path)

    if event_type == "deleted":
        logger.info("[DELETED] {}", os.path.basename(normalized_path))
        _log_event(cur, "deleted", normalized_path)
        _delete_file(cur, normalized_path)
    else:
        try:
            if not os.path.exists(normalized_path):
                conn.close()
                return
            stat      = os.stat(normalized_path)
            file_hash, chunk_hashes = compute_file_and_chunk_hashes(normalized_path, config.CHUNK_SIZE)

            if not file_hash:
                conn.close()
                return

            cur.execute("SELECT hash, version_id FROM files WHERE file_path = ?", (normalized_path,))
            row = cur.fetchone()

            db_hash = row[0] if row else None
            version_id = row[1] if row else 0

            if row is None:
                logger.info("[NEW] {} at {}", os.path.basename(normalized_path), time.time())
                _log_event(cur, "new", normalized_path, file_hash, version_id)
            elif db_hash != file_hash:
                logger.info("[MODIFIED] {} at {}", os.path.basename(normalized_path), time.time())
                _log_event(cur, "modified", normalized_path, file_hash, version_id)
            else:
                logger.debug("[IGNORED] {} unchanged at {}", os.path.basename(normalized_path), time.time())
                conn.close()
                return

            cur.execute("""
                INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id)
                VALUES (?, ?, ?, ?, ?)
            """, (normalized_path, file_hash, stat.st_size, stat.st_mtime, version_id))

            update_chunk_signatures(cur, normalized_path, chunk_hashes)

        except OSError:
            conn.close()
            return

    conn.commit()
    conn.close()


def run_full_scan():
    """Bootstrap scanner that catches changes made while agent daemon was completely dark."""
    from watcher import is_ignored
    ensure_db()

    from state import is_local_mutation_active
    if is_local_mutation_active():
        return

    if not os.path.exists(config.WATCH_DIR):
        os.makedirs(config.WATCH_DIR)

    conn = get_db_connection(timeout=30.0)
    cur  = conn.cursor()
    cur.execute("SELECT file_path, hash, version_id FROM files")
    db_records = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    conn.close()

    current_paths = set()

    for root, _, files in os.walk(config.WATCH_DIR):
        for file in files:
            full_path = os.path.normpath(os.path.join(root, file))
            if is_ignored(full_path):
                continue
            current_paths.add(full_path)

            try:
                stat = os.stat(full_path)
                h, chunk_hashes = compute_file_and_chunk_hashes(full_path, config.CHUNK_SIZE)
                if not h:
                    continue

                if full_path not in db_records:
                    logger.info("[BOOTSTRAP FIND] New entry -> {}", file)
                    conn_file = get_db_connection()
                    cur_file = conn_file.cursor()
                    _log_event(cur_file, "new", full_path, h, 0)
                    cur_file.execute("INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id) VALUES (?, ?, ?, ?, ?)",
                                (full_path, h, stat.st_size, stat.st_mtime, 0))
                    update_chunk_signatures(cur_file, full_path, chunk_hashes)
                    conn_file.commit()
                    conn_file.close()
                elif db_records[full_path][0] != h:
                    logger.info("[BOOTSTRAP FIND] Modified entry -> {}", file)
                    conn_file = get_db_connection()
                    cur_file = conn_file.cursor()
                    _log_event(cur_file, "modified", full_path, h, db_records[full_path][1])
                    cur_file.execute("INSERT OR REPLACE INTO files (file_path, hash, size, last_modified, version_id) VALUES (?, ?, ?, ?, ?)",
                                (full_path, h, stat.st_size, stat.st_mtime, db_records[full_path][1]))
                    update_chunk_signatures(cur_file, full_path, chunk_hashes)
                    conn_file.commit()
                    conn_file.close()
            except OSError:
                continue

    for tracked_path in db_records:
        normalized_tracked = os.path.normpath(tracked_path)
        if normalized_tracked not in current_paths:
            logger.info("[BOOTSTRAP FIND] Vanished entry -> {}", os.path.basename(normalized_tracked))
            conn_file = get_db_connection()
            cur_file = conn_file.cursor()
            _log_event(cur_file, "deleted", normalized_tracked, None, db_records[tracked_path][1])
            cur_file.execute("DELETE FROM files WHERE file_path = ?", (normalized_tracked,))
            cur_file.execute("DELETE FROM chunk_signatures WHERE file_path = ?", (normalized_tracked,))
            conn_file.commit()
            conn_file.close()
