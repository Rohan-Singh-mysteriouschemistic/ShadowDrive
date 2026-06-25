class TestHealthCheck:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestMetadataDiff:
    def test_diff_unauthenticated(self, client):
        response = client.get("/sync/metadata/diff?device_id=1")
        assert response.status_code == 401

    def test_diff_empty_state(self, client, auth_headers, db_session):
        from app import models
        user = db_session.query(models.User).first()
        assert user is not None
        device_resp = client.post(
            "/devices/register",
            json={"user_id": user.id, "device_name": "test-device"},
        )
        assert device_resp.status_code == 201
        device_id = device_resp.json()["id"]

        response = client.get(
            f"/sync/metadata/diff?device_id={device_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["missing_files"] == []
        assert data["outdated_files"] == []
        assert data["deleted_files"] == []


class TestConflictsEndpoint:
    def test_conflicts_no_auth(self, client):
        response = client.get("/sync/conflicts")
        assert response.status_code == 401

    def test_conflicts_empty(self, client, auth_headers):
        response = client.get("/sync/conflicts", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []


class TestFileUpload:
    def test_announce_metadata(self, client, auth_headers):
        response = client.post(
            "/sync/announce",
            json={"path": "test.txt", "hash": "abc123def456", "event": "new"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "accepted"
        assert data["upload_required"] is True
        assert "file_id" in data
        assert "version_id" in data
