"""
End-to-end pipeline test: register -> session -> upload -> process ->
generate (Demo Mode, no live API key/cost) -> PDF export -> download.
Exercises the full request path through main.py rather than any single
module in isolation.
"""
import time

from fastapi.testclient import TestClient


def _poll(fn, predicate, timeout_s: float = 20.0, interval_s: float = 0.2):
    deadline = time.monotonic() + timeout_s
    result = fn()
    while not predicate(result) and time.monotonic() < deadline:
        time.sleep(interval_s)
        result = fn()
    assert predicate(result), f"Polling timed out with last result: {result}"
    return result


def test_full_pipeline_upload_to_pdf(client: TestClient, register_and_login) -> None:
    headers, _, _ = register_and_login()

    # 1. Session
    session_id = client.post("/api/sessions", headers=headers).json()["session_id"]

    # 2. Upload a small sample document
    upload = client.post(
        f"/api/sessions/{session_id}/documents",
        headers=headers,
        files={"files": ("acme_overview.txt", b"Acme Corp generated $22M revenue with 40 employees in 2024.", "text/plain")},
    )
    assert upload.status_code == 200

    # 3. Process (background task; poll until ready)
    proc_start = client.post(f"/api/sessions/{session_id}/process", headers=headers)
    assert proc_start.status_code == 200
    _poll(
        lambda: client.get(f"/api/sessions/{session_id}/process/status", headers=headers).json(),
        lambda r: r["status"] in ("ready", "error"),
    )
    status = client.get(f"/api/sessions/{session_id}/process/status", headers=headers).json()
    assert status["status"] == "ready", status

    # 4. Switch this user to Demo Mode so generation is instant, free, and offline
    cfg = client.put("/api/config", headers=headers, json={"llm_provider": "demo"})
    assert cfg.status_code == 200

    # 5. Generate one section (keep the test fast) and poll to completion
    gen_start = client.post(
        f"/api/sessions/{session_id}/generate-all",
        headers=headers,
        json={"sections": ["executive_summary"]},
    )
    assert gen_start.status_code == 200
    _poll(
        lambda: client.get(f"/api/sessions/{session_id}/generate-all/status", headers=headers).json(),
        lambda r: r["status"] in ("generated", "error"),
    )
    gen_status = client.get(f"/api/sessions/{session_id}/generate-all/status", headers=headers).json()
    assert gen_status["status"] == "generated", gen_status
    assert "executive_summary" in gen_status["sections_ready"]

    # 6. Export to PDF and poll to completion
    pdf_start = client.post(f"/api/sessions/{session_id}/generate-pdf", headers=headers)
    assert pdf_start.status_code == 200
    _poll(
        lambda: client.get(f"/api/sessions/{session_id}/generate-pdf/status", headers=headers).json(),
        lambda r: r["status"] in ("ready", "error"),
    )
    pdf_status = client.get(f"/api/sessions/{session_id}/generate-pdf/status", headers=headers).json()
    assert pdf_status["status"] == "ready", pdf_status
    assert pdf_status["pdf_password"]  # confidential export is password-protected

    # 7. Download the finished, password-protected PDF
    download = client.get(f"/api/sessions/{session_id}/download-pdf", headers=headers)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert len(download.content) > 1000

    # 8. Audit trail recorded the key actions for this user
    audit = client.get("/api/audit/me", headers=headers)
    assert audit.status_code == 200
    actions = {e["action"] for e in audit.json()["events"]}
    assert {"register", "login", "session_create", "document_upload", "config_update", "pdf_download"} <= actions
