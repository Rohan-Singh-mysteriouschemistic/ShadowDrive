import sqlite3

import pytest

from database import close_connection, get_connection


class TestDatabaseConnection:
    def test_get_connection_returns_sqlite3_connection(self):
        conn = get_connection()
        assert isinstance(conn, sqlite3.Connection)

    def test_wal_mode_is_enabled(self):
        conn = get_connection()
        cur = conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        assert "wal" in mode.lower()

    def test_busy_timeout_is_set(self):
        conn = get_connection()
        cur = conn.execute("PRAGMA busy_timeout")
        timeout = cur.fetchone()[0]
        assert timeout == 5000

    def test_connection_is_thread_local(self):
        c1 = get_connection()
        c2 = get_connection()
        assert c1 is c2

    def test_tables_can_be_created_and_queried(self):
        conn = get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test_table (val) VALUES (?)", ("hello",))
        cur = conn.execute("SELECT val FROM test_table")
        assert cur.fetchone()[0] == "hello"
        conn.execute("DROP TABLE test_table")

    def test_close_connection_clears_thread_local(self):
        conn = get_connection()
        assert conn is not None
        close_connection()
        new_conn = get_connection()
        assert new_conn is not conn
