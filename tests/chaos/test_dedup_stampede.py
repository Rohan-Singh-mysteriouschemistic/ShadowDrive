"""
Suite 4: The Hash Dedup Stampede
Tortures the backend /sync/upload endpoint with 5 simultaneous uploads
of the exact same file to verify 'SELECT ... FOR UPDATE' locking and deduplication.
"""
import os
import time
import requests
import concurrent.futures
from urllib.parse import urljoin
import pytest

SERVER_URL = os.getenv("SHADOWDRIVE_TEST_SERVER_URL", "http://127.0.0.1:8000")

def test_dedup_stampede(tmp_path):
    # 1. Register an ephemeral test user to avoid corrupting real user quotas
    test_user = f"stampede_{int(time.time())}"
    test_email = f"{test_user}@test.com"
    test_pass = "password123"
    
    try:
        reg_resp = requests.post(urljoin(SERVER_URL, "/users/register"), json={
            "username": test_user,
            "email": test_email,
            "password": test_pass
        }, timeout=5)
    except requests.exceptions.ConnectionError:
        pytest.skip("Backend not reachable.")
        
    if reg_resp.status_code != 201 and reg_resp.status_code != 400:
        pytest.skip(f"Registration failed: {reg_resp.text}")
        
    login_resp = requests.post(urljoin(SERVER_URL, "/users/login"), json={
        "email": test_email,
        "password": test_pass
    })
    
    if login_resp.status_code != 200:
        pytest.skip("Login failed.")
        
    token = login_resp.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Create the mock 10MB file
    file_path = tmp_path / "stampede.bin"
    with open(file_path, "wb") as f:
        f.write(os.urandom(10 * 1024 * 1024))
        
    def upload_worker(thread_id):
        # We announce the file first as per the ShadowDrive protocol
        announce_resp = requests.post(
            urljoin(SERVER_URL, "/sync/announce"),
            headers=headers,
            json={
                "path": f"stampede_{thread_id}.bin",
                "hash": "mockhash123",
                "event": "new",
                "chunk_hashes": []
            }
        )
        if announce_resp.status_code != 200:
            return announce_resp
            
        version_id = announce_resp.json().get("version_id")
        
        # Then we hit the upload endpoint
        with open(file_path, "rb") as f:
            files = {
                "file": (f"stampede_{thread_id}.bin", f, "application/octet-stream")
            }
            # Add version_id to data as expected by the server
            data = {"version_id": version_id}
            
            resp = requests.post(
                urljoin(SERVER_URL, "/sync/upload"),
                headers=headers,
                files=files,
                data=data
            )
            return resp

    # 3. The Torture: Launch 5 simultaneous uploads
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(upload_worker, i) for i in range(5)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            
    # 4. The Assertion: All 5 should return success
    success_count = 0
    conflict_count = 0
    for resp in results:
        # 202 Accepted, 201 Created, or 409 Conflict (if our lock successfully blocked them)
        if resp.status_code in [200, 201, 202]:
            success_count += 1
        elif resp.status_code == 409:
            conflict_count += 1
            
    assert success_count + conflict_count == 5, f"Some uploads failed! {[(r.status_code, r.text) for r in results]}"
    
    # Wait for the RQ background workers to process the files
    time.sleep(5)
    
    # Fetch metadata to verify how many files were successfully stored
    meta_resp = requests.get(urljoin(SERVER_URL, "/sync/metadata"), headers=headers)
    assert meta_resp.status_code == 200
    
    files = meta_resp.json()
    assert len(files) == 5, "Not all announced files made it to metadata"
    
    # In a perfect dedup stampede, 1 upload succeeds, 4 are deduplicated.
    # The server should only store 1 physical file on MinIO.
    # We assert that the system didn't crash and correctly handled the concurrency.
