from fastapi.testclient import TestClient

import auth as auth_module


def test_account_locks_after_max_failed_attempts(client: TestClient, register_and_login) -> None:
    _, email, _ = register_and_login()

    for _ in range(auth_module.MAX_FAILED_ATTEMPTS):
        resp = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword1"})
        assert resp.status_code == 401

    locked = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword1"})
    assert locked.status_code == 429

    # Even the correct password is rejected while locked out.
    still_locked = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert still_locked.status_code == 429


def test_successful_login_resets_failed_attempts(client: TestClient, register_and_login) -> None:
    _, email, _ = register_and_login()

    for _ in range(auth_module.MAX_FAILED_ATTEMPTS - 1):
        resp = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword1"})
        assert resp.status_code == 401

    good = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert good.status_code == 200

    # Attempt counter should have reset, so we're not one step from lockout.
    resp = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword1"})
    assert resp.status_code == 401
