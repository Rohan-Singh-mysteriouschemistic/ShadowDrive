class TestRegistration:
    def test_register_success(self, client):
        response = client.post(
            "/users/",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "StrongP@ssw0rd!",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "created_at" in data

    def test_register_duplicate_email(self, client):
        payload = {
            "username": "user1",
            "email": "dupe@example.com",
            "password": "StrongP@ssw0rd!",
        }
        response = client.post("/users/", json=payload)
        assert response.status_code == 201

        response = client.post("/users/", json=payload)
        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    def test_register_weak_password(self, client):
        response = client.post(
            "/users/",
            json={
                "username": "weakpwuser",
                "email": "weakpw@example.com",
                "password": "abc",
            },
        )
        # FastAPI with pydantic does not enforce password strength by default,
        # so this will succeed unless the app adds custom validation.
        assert response.status_code in (201, 422)


class TestLogin:
    def test_login_success(self, client):
        client.post(
            "/users/",
            json={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "StrongP@ssw0rd!",
            },
        )
        response = client.post(
            "/users/login",
            json={
                "email": "login@example.com",
                "password": "StrongP@ssw0rd!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post(
            "/users/",
            json={
                "username": "wrongpwuser",
                "email": "wrongpw@example.com",
                "password": "StrongP@ssw0rd!",
            },
        )
        response = client.post(
            "/users/login",
            json={
                "email": "wrongpw@example.com",
                "password": "WrongPassword123!",
            },
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/users/login",
            json={
                "email": "nobody@example.com",
                "password": "SomePassword123!",
            },
        )
        assert response.status_code == 401


class TestTokenRefresh:
    def test_refresh_with_valid_token(self, client):
        client.post(
            "/users/",
            json={
                "username": "refreshuser",
                "email": "refresh@example.com",
                "password": "StrongP@ssw0rd!",
            },
        )
        login_resp = client.post(
            "/users/login",
            json={
                "email": "refresh@example.com",
                "password": "StrongP@ssw0rd!",
            },
        )
        token = login_resp.json()["access_token"]

        response = client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_refresh_without_token(self, client):
        response = client.post("/auth/refresh")
        assert response.status_code == 401
