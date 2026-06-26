import pytest
from datetime import datetime, timezone, timedelta
from app import models

def test_resolve_client_wins_copies_chunks(client, auth_headers, db_session):
    # 1. Announce a file and make it complete on the server (version 1)
    response = client.post(
        "/sync/announce",
        json={
            "path": "Earth View.heic",
            "hash": "server_hash_1",
            "event": "new",
            "chunk_hashes": ["chunk_hash_a", "chunk_hash_b"]
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    v1_id = data["version_id"]

    # Mark the version 1 completed in database (simulating completed upload)
    v1 = db_session.query(models.Version).filter(models.Version.id == v1_id).first()
    v1.size_bytes = 22747420
    v1.upload_status = models.UploadStatus.complete

    # Add chunk records manually to simulate successful chunk upload
    db_session.add(models.VersionChunk(version_id=v1_id, chunk_index=0, chunk_hash="chunk_hash_a"))
    db_session.add(models.VersionChunk(version_id=v1_id, chunk_index=1, chunk_hash="chunk_hash_b"))
    db_session.commit()

    # 1.5. Announce and complete version 2 on the server (simulating someone else uploaded version 2)
    response_v2 = client.post(
        "/sync/announce",
        json={
            "path": "Earth View.heic",
            "hash": "server_hash_2",
            "event": "modified",
            "base_version_id": v1_id,
            "chunk_hashes": ["chunk_hash_e", "chunk_hash_f"]
        },
        headers=auth_headers
    )
    assert response_v2.status_code == 201
    v2_id = response_v2.json()["version_id"]
    v2 = db_session.query(models.Version).filter(models.Version.id == v2_id).first()
    v2.size_bytes = 22747420
    v2.upload_status = models.UploadStatus.complete
    db_session.add(models.VersionChunk(version_id=v2_id, chunk_index=0, chunk_hash="chunk_hash_e"))
    db_session.add(models.VersionChunk(version_id=v2_id, chunk_index=1, chunk_hash="chunk_hash_f"))
    db_session.commit()

    # 2. Trigger a conflict where the client wins (LWW)
    # Client modified time is later than server modified time
    server_time = v2.announced_at or v2.created_at
    client_time = server_time + timedelta(minutes=5)

    # Announce new metadata from client with base_version_id = v1_id (outdated base), creating conflict
    response2 = client.post(
        "/sync/announce",
        json={
            "path": "Earth View.heic",
            "hash": "client_hash_3",
            "event": "modified",
            "base_version_id": v1_id,
            "client_modified_at": client_time.isoformat(),
            "chunk_hashes": ["chunk_hash_c", "chunk_hash_d"]
        },
        headers=auth_headers
    )
    assert response2.status_code == 201
    data2 = response2.json()
    assert data2["status"] == "conflict_resolved"

    conflict_info = data2["conflict_info"]
    conflict_version_id = conflict_info["conflict_version_id"]
    winner_version_id = conflict_info["winner_version_id"]

    # Verify that conflict_version has the cloned chunks from v2 (server_latest)
    conflict_chunks = db_session.query(models.VersionChunk).filter(
        models.VersionChunk.version_id == conflict_version_id
    ).order_by(models.VersionChunk.chunk_index).all()

    assert len(conflict_chunks) == 2
    assert conflict_chunks[0].chunk_index == 0
    assert conflict_chunks[0].chunk_hash == "chunk_hash_e"
    assert conflict_chunks[1].chunk_index == 1
    assert conflict_chunks[1].chunk_hash == "chunk_hash_f"

    # Verify that the winner version does not have cloned chunks
    v3 = db_session.query(models.Version).filter(models.Version.id == winner_version_id).first()
    assert v3.upload_status == models.UploadStatus.pending

