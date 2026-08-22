from fastapi.testclient import TestClient


def _new_session(client: TestClient, headers: dict) -> str:
    resp = client.post("/api/sessions", headers=headers)
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_path_traversal_filename_rejected(client: TestClient, register_and_login) -> None:
    headers, _, _ = register_and_login()
    session_id = _new_session(client, headers)

    resp = client.post(
        f"/api/sessions/{session_id}/documents",
        headers=headers,
        files={"files": ("../../../../etc/passwd", b"malicious", "text/plain")},
    )
    # Starlette/httpx normalize ".." in the multipart filename to its basename
    # ("passwd", no extension), so this is rejected either for the invalid
    # name or for the missing/unsupported extension — either way it must
    # never escape the session's upload directory.
    assert resp.status_code in (200, 400, 415)
    if resp.status_code == 200:
        for f in resp.json()["files"]:
            assert ".." not in f["name"]
            assert "/" not in f["name"] and "\\" not in f["name"]


def test_disallowed_extension_rejected(client: TestClient, register_and_login) -> None:
    headers, _, _ = register_and_login()
    session_id = _new_session(client, headers)

    resp = client.post(
        f"/api/sessions/{session_id}/documents",
        headers=headers,
        files={"files": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_oversized_file_rejected(client: TestClient, register_and_login, monkeypatch) -> None:
    import config

    monkeypatch.setattr(config.settings, "max_upload_mb", 0)  # anything nonempty now exceeds the limit
    headers, _, _ = register_and_login()
    session_id = _new_session(client, headers)

    resp = client.post(
        f"/api/sessions/{session_id}/documents",
        headers=headers,
        files={"files": ("report.txt", b"some content", "text/plain")},
    )
    assert resp.status_code == 413


def test_valid_upload_accepted(client: TestClient, register_and_login) -> None:
    headers, _, _ = register_and_login()
    session_id = _new_session(client, headers)

    resp = client.post(
        f"/api/sessions/{session_id}/documents",
        headers=headers,
        files={"files": ("company_overview.txt", b"Acme Corp overview.", "text/plain")},
    )
    assert resp.status_code == 200
    assert resp.json()["uploaded"] == 1
