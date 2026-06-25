import os

import pytest

from hash_utils import (
    EMPTY_FILE_SHA256,
    chunk_and_hash_file,
    compute_file_and_chunk_hashes,
    hash_file,
)


class TestHashFile:
    def test_hash_existing_file_returns_64_char_hex(self, sample_file):
        digest = hash_file(sample_file)
        assert digest is not None
        assert isinstance(digest, str)
        assert len(digest) == 64
        int(digest, 16)

    def test_hash_nonexistent_file_returns_none(self):
        result = hash_file("/nonexistent/path/file.txt")
        assert result is None

    def test_hash_is_deterministic(self, sample_file):
        h1 = hash_file(sample_file)
        h2 = hash_file(sample_file)
        assert h1 == h2

    def test_hash_changes_when_content_changes(self, sample_file):
        h1 = hash_file(sample_file)
        with open(sample_file, "a") as f:
            f.write("more content")
        h2 = hash_file(sample_file)
        assert h1 != h2

    def test_hash_empty_file_returns_known_hash(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        digest = hash_file(str(empty))
        assert digest == EMPTY_FILE_SHA256


class TestChunkAndHashFile:
    def test_returns_list_of_hashes(self, sample_file):
        hashes = chunk_and_hash_file(sample_file)
        assert isinstance(hashes, list)
        assert len(hashes) > 0
        for h in hashes:
            assert len(h) == 64
            int(h, 16)

    def test_empty_file_returns_empty_hash_list(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        hashes = chunk_and_hash_file(str(empty))
        assert hashes == [EMPTY_FILE_SHA256]

    def test_nonexistent_file_returns_empty_file_hash(self):
        result = chunk_and_hash_file("/nonexistent/path/file.txt")
        assert result == [EMPTY_FILE_SHA256]


class TestComputeFileAndChunkHashes:
    def test_returns_tuple_of_file_hash_and_chunk_hashes(self, sample_file):
        file_hash, chunk_hashes = compute_file_and_chunk_hashes(sample_file, 4096)
        assert isinstance(file_hash, str)
        assert len(file_hash) == 64
        assert isinstance(chunk_hashes, list)
        assert len(chunk_hashes) > 0

    def test_empty_file_returns_known_hashes(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        file_hash, chunk_hashes = compute_file_and_chunk_hashes(str(empty), 4096)
        assert file_hash == EMPTY_FILE_SHA256
        assert chunk_hashes == [EMPTY_FILE_SHA256]

    def test_deterministic(self, sample_file):
        r1 = compute_file_and_chunk_hashes(sample_file, 4096)
        r2 = compute_file_and_chunk_hashes(sample_file, 4096)
        assert r1 == r2
