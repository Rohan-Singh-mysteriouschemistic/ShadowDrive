import os
os.environ["SECRET_KEY"] = "test-secret-key-for-shadowdrive-tests"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from contextlib import asynccontextmanager
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, BigInteger
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from unittest.mock import patch, MagicMock
import pytest

from app.main import app
from app.database import get_db
from app import models


@compiles(BigInteger, "sqlite")
def compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


@asynccontextmanager
async def noop_lifespan(app):
    yield


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    async def always_true(ip: str) -> bool:
        return True
    with patch("app.routers.auth.rate_limiter.check_rate_limit", always_true):
        yield


@pytest.fixture(autouse=True)
def mock_minio():
    mock_s3 = MagicMock()
    with patch("app.storage._get_s3_client", return_value=mock_s3):
        yield


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def db_session(db_path):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.router.lifespan_context = noop_lifespan
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client, db_session):
    response = client.post(
        "/users/",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "StrongP@ssw0rd!",
        },
    )
    assert response.status_code == 201

    response = client.post(
        "/users/login",
        json={
            "email": "test@example.com",
            "password": "StrongP@ssw0rd!",
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(client):
    return client
