"""
database.py — Thread-safe SQLite Connection Pool with WAL Mode

Provides get_connection() which returns a thread-local connection
with WAL mode, busy_timeout, and NORMAL synchronous mode enabled.
"""

import sqlite3
import threading

import config

_thread_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get or create a thread-local SQLite connection with WAL mode."""
    conn = getattr(_thread_local, "connection", None)
    if conn is not None:
        try:
            conn.total_changes
        except sqlite3.ProgrammingError:
            conn = None

    if conn is None:
        conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        _thread_local.connection = conn
    return conn


def close_connection():
    """Close the thread-local connection if it exists."""
    conn = getattr(_thread_local, "connection", None)
    if conn is not None:
        conn.close()
        _thread_local.connection = None
