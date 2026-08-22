from fastapi.testclient import TestClient


def test_register_login_me(client: TestClient, register_and_login) -> None:
    headers, email, user_id = register_and_login()

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"].lower() == email
    assert me.json()["id"] == user_id


def test_duplicate_email_rejected(client: TestClient, register_and_login) -> None:
    headers, email, _ = register_and_login()
    dup = client.post(
        "/api/auth/register",
        json={"email": email, "name": "Someone Else", "password": "StrongPass123!"},
    )
    assert dup.status_code == 409


def test_wrong_password_rejected(client: TestClient, register_and_login) -> None:
    _, email, _ = register_and_login()
    bad = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword1"})
    assert bad.status_code == 401


def test_session_ownership_enforced_across_users(client: TestClient, register_and_login) -> None:
    headers_a, _, _ = register_and_login()
    headers_b, _, _ = register_and_login()

    created = client.post("/api/sessions", headers=headers_a)
    session_id = created.json()["session_id"]

    cross_access = client.get(f"/api/sessions/{session_id}", headers=headers_b)
    assert cross_access.status_code == 403

    own_access = client.get(f"/api/sessions/{session_id}", headers=headers_a)
    assert own_access.status_code == 200


def test_unauthenticated_request_rejected(client: TestClient) -> None:
    resp = client.get("/api/sessions")
    assert resp.status_code == 401
