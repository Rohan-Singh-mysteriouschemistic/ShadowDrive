"""
Tests for concurrent pipeline improvements: PathLock, CircuitBreakerOpen, and Hash Cache.
"""
import os
import sys
import time
import pytest
import threading
from pathlib import Path
from unittest.mock import MagicMock

CLIENT_DIR = Path(__file__).resolve().parent.parent.parent / "Client-Logic"
sys.path.append(str(CLIENT_DIR))

import resilient_http
import sync_engine
import config


def test_path_lock_serialization():
    """Verify that PathLock serializes operations on the same path, but allows concurrency on different paths."""
    lock_records = []
    
    path_a = "file_a.txt"
    path_b = "file_b.txt"
    
    # Run two threads on path_a, and one on path_b
    def worker_a1():
        with sync_engine.PathLock(path_a):
            lock_records.append("a1_start")
            time.sleep(0.1)
            lock_records.append("a1_end")
            
    def worker_a2():
        time.sleep(0.02)  # ensure worker_a1 starts first
        with sync_engine.PathLock(path_a):
            lock_records.append("a2_start")
            lock_records.append("a2_end")
            
    def worker_b():
        time.sleep(0.02)  # starts concurrently with worker_a1
        with sync_engine.PathLock(path_b):
            lock_records.append("b_start")
            time.sleep(0.05)
            lock_records.append("b_end")

    t1 = threading.Thread(target=worker_a1)
    t2 = threading.Thread(target=worker_a2)
    t3 = threading.Thread(target=worker_b)
    
    t1.start()
    t2.start()
    t3.start()
    
    t1.join()
    t2.join()
    t3.join()
    
    # Check that a1 and a2 are strictly serialized
    a1_start_idx = lock_records.index("a1_start")
    a1_end_idx = lock_records.index("a1_end")
    a2_start_idx = lock_records.index("a2_start")
    a2_end_idx = lock_records.index("a2_end")
    
    assert a1_end_idx < a2_start_idx, "PathLock did not serialize operations on the same path!"
    
    # Check that worker_b started concurrently (before worker_a1 finished)
    b_start_idx = lock_records.index("b_start")
    assert b_start_idx < a1_end_idx, "PathLock blocked a different path!"


def test_circuit_breaker_fail_fast(mocker):
    """Verify that resilient_http raises CircuitBreakerOpen immediately when circuit is open."""
    # Reset and trip the circuit breaker
    resilient_http._circuit.record_success()
    for _ in range(resilient_http._circuit.failure_threshold):
        resilient_http._circuit.record_failure()
        
    assert resilient_http._circuit.state == resilient_http.CircuitState.OPEN
    
    # Try requesting. It should immediately raise CircuitBreakerOpen without sleeping
    start_time = time.time()
    with pytest.raises(resilient_http.CircuitBreakerOpen):
        resilient_http.request("GET", "http://any-domain-does-not-matter.com/test")
        
    duration = time.time() - start_time
    assert duration < 0.1, f"Expected fast fail-fast, but it took {duration:.2f}s (likely slept)"
    
    # Reset it back
    resilient_http._circuit.record_success()


def test_prepared_hash_caching(mocker):
    """Verify that get_prepared_encrypted_hashes caches calls and avoids duplicate pass calculations."""
    sync_engine._enc_hash_cache.clear()
    
    # Mock prepare_encrypted_hashes
    mock_prep = mocker.patch('sync_engine.prepare_encrypted_hashes', return_value=("mock_file_hash", ["chunk1", "chunk2"]))
    
    path = "dummy_file.txt"
    plaintext_hash = "abc123plaintext"
    
    # First call - should call the mock
    hash_file1, chunk_hashes1 = sync_engine.get_prepared_encrypted_hashes(path, plaintext_hash)
    assert mock_prep.call_count == 1
    assert hash_file1 == "mock_file_hash"
    assert chunk_hashes1 == ["chunk1", "chunk2"]
    
    # Second call - should fetch from cache without calling the mock again
    hash_file2, chunk_hashes2 = sync_engine.get_prepared_encrypted_hashes(path, plaintext_hash)
    assert mock_prep.call_count == 1  # Still 1!
    assert hash_file2 == "mock_file_hash"
    assert chunk_hashes2 == ["chunk1", "chunk2"]


def test_upload_job_abort_propagation(mocker):
    """Verify that setting the abort event on UploadJob prevents subsequent chunk uploads."""
    job = sync_engine.UploadJob(
        local_path="dummy_path.bin",
        remote_path="dummy_path.bin",
        file_hash="fakehash",
        version_id=100,
        file_size=1024,
        event_id=1
    )
    
    # Mark job as aborted
    job.aborted.set()
    
    # Mock network request to ensure it is NOT called
    mock_request = mocker.patch('network_client._request')
    
    completed_lock = threading.Lock()
    
    # Run chunk worker - should exit immediately because job is aborted
    sync_engine._upload_chunk_worker(
        job, chunk_index=0, total_chunks=1,
        expected_plain_hash="fakehash", file_hash_to_send="fakehash",
        completed_lock=completed_lock
    )
    
    assert mock_request.call_count == 0
    assert len(job.completed_chunks or set()) == 0
