"""
Suite 2: The Network Guillotine
Tests Zero-Failure chunked upload recovery and the CircuitBreaker logic.
"""
import os
import pytest
import requests
import sys
from pathlib import Path
from unittest.mock import MagicMock

CLIENT_DIR = Path(__file__).resolve().parent.parent.parent / "Client-Logic"
sys.path.append(str(CLIENT_DIR))

# pyrefly: ignore [missing-import]
import resilient_http
# pyrefly: ignore [missing-import]
import network_client
# pyrefly: ignore [missing-import]
import config
import sync_engine

@pytest.fixture
def mock_session(mocker):
    """Mocks resilient_http._get_session to return our controlled session."""
    session_mock = MagicMock()
    mocker.patch('resilient_http._get_session', return_value=session_mock)
    
    # We must reset the singleton circuit breaker before the test
    resilient_http._circuit.record_success() 
    return session_mock

def test_chunked_upload_network_drop(mock_session, tmp_path, mocker):
    """
    Simulates a ConnectionResetError specifically on chunk #3 during a 50MB upload.
    Asserts exponential backoff and correct chunk resumption.
    """
    file_size = 50 * 1024 * 1024
    
    # Create a dummy 50MB file
    dummy_file = tmp_path / "mock_50MB.bin"
    with open(dummy_file, "wb") as f:
        f.write(os.urandom(file_size))
        
    job = sync_engine.UploadJob(
        local_path=str(dummy_file),
        remote_path="mock_50MB.bin",
        file_hash="fakehash",
        version_id=123,
        file_size=file_size,
        event_id=1,
        plaintext_hash="fakehash",
        missing_chunks=list(range(13)),
        completed_chunks=set(),
        file_id=1
    )
    
    # We want to throw a ConnectionResetError on chunk #3.
    # We will track how many times `request` is called.
    call_tracker = {"total_calls": 0, "chunk_3_failures": 0}
    
    def side_effect_request(method, url, **kwargs):
        call_tracker["total_calls"] += 1
        
        # resilient_http sends chunk_index in kwargs["data"]["chunk_index"]
        data = kwargs.get("data", {})
        chunk_index = int(data.get("chunk_index", -1))
        
        # If this is chunk #3, simulate network drop
        if chunk_index == 3:
            # We fail 4 times so resilient_http recovers on its 5th attempt
            if call_tracker["chunk_3_failures"] < 4:
                call_tracker["chunk_3_failures"] += 1
                raise requests.exceptions.ConnectionError("Connection reset by peer")
                
        # For all other chunks (and chunk 3 after 4 failures), return success
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "ok"}
        return resp
        
    mock_session.request.side_effect = side_effect_request
    
    # Speed up the circuit breaker and retry policy to avoid waiting 30s in tests
    mocker.patch('resilient_http._default_policy.base_delay', 0.01)
    mocker.patch('resilient_http._default_policy.max_delay', 0.1)
    mocker.patch('resilient_http._circuit.recovery_timeout', 0.2)
    
    # Mock db finalization so we don't need a real db
    mocker.patch('sync_engine.finalize_local_db_after_upload')
    mocker.patch('sync_engine._ack_upload')
    mocker.patch('sync_engine._mark_synced_db')
    mocker.patch('sync_engine._clear_in_flight')
    
    # Ensure network_client uses our mocked URL and token
    mocker.patch('network_client._get_token', return_value="mockjwt")
    config.SERVER_URL = "http://mockserver"  
    
    try:
        sync_engine._upload_chunks_resilient(job, expected_plain_hash="fakehash")
    except Exception as e:
        pytest.fail(f"Upload failed entirely instead of recovering: {e}")
        
    # Assertions
    # The CircuitBreaker should have tripped and recovered
    assert call_tracker["chunk_3_failures"] == 4, "Did not hit the targeted chunk failure"
    
    # Number of chunks is 13. We failed 4 times on chunk 3. 
    # Total calls should be 13 success + 4 failures = 17 calls.
    assert call_tracker["total_calls"] == 17, f"Expected 17 API calls, got {call_tracker['total_calls']}"
    
    # Verify job tracking is correct — all chunks complete
    assert len(job.completed_chunks) == 13, "Not all chunks were marked complete"
    assert 3 in job.completed_chunks, "Chunk 3 was not completed after recovery"
    
    # Verify CircuitBreaker recovered to CLOSED
    assert resilient_http._circuit.state == resilient_http.CircuitState.CLOSED, "Circuit breaker did not reset"
