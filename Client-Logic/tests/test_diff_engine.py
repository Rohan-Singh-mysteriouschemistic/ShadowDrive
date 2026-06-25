import os

import pytest
from diff_engine import ensure_db, get_db_connection, process_single_file


class TestEnsureDb:
    def test_ensure_db_creates_required_tables(self):
        ensure_db()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        expected = {"files", "events", "chunk_signatures", "settings",
                     "pending_chunk_uploads", "local_chunk_nonces"}
        for t in expected:
            assert t in tables, f"Missing table: {t}"
        conn.close()

    def test_ensure_db_is_idempotent(self):
        ensure_db()
        ensure_db()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count = cur.fetchone()[0]
        assert count >= 6
        conn.close()


class TestProcessSingleFile:
    def test_process_single_file_created_creates_event(self, sample_file):
        ensure_db()
        process_single_file(sample_file, "created")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT event_type, file_path FROM events")
        rows = cur.fetchall()
        conn.close()
        assert len(rows) >= 1
        event_types = [r[0] for r in rows]
        assert "new" in event_types

    def test_process_single_file_deleted_creates_event(self, sample_file):
        ensure_db()
        process_single_file(sample_file, "deleted")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT event_type, file_path FROM events")
        rows = cur.fetchall()
        conn.close()
        assert len(rows) >= 1
        matching = [r for r in rows if r[0] == "deleted"]
        assert len(matching) >= 1

    def test_process_single_file_created_records_file_in_files_table(self, sample_file):
        ensure_db()
        process_single_file(sample_file, "created")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT file_path, hash FROM files WHERE file_path = ?",
                    (os.path.normpath(sample_file),))
        row = cur.fetchone()
        conn.close()
        assert row is not None
        assert row[1] is not None
        assert len(row[1]) == 64

    def test_process_single_file_deleted_removes_from_files_table(self, sample_file):
        ensure_db()
        process_single_file(sample_file, "created")
        process_single_file(sample_file, "deleted")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM files WHERE file_path = ?",
                    (os.path.normpath(sample_file),))
        row = cur.fetchone()
        conn.close()
        assert row is None
