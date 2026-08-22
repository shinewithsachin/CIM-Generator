import uuid

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from main import app


def test_health_endpoint_integration() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert "X-Request-ID" in response.headers


def test_register_login_integration() -> None:
    client = TestClient(app)
    email = f"integration_{uuid.uuid4().hex[:8]}@example.com"

    register = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "name": "Integration User",
            "password": "StrongPass123",
        },
    )
    assert register.status_code == 201

    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert login.status_code == 200
    body = login.json()
    assert "token" in body
    assert body["user"]["email"].lower() == email
