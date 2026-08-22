from pathlib import Path


def test_auth_endpoints_are_declared() -> None:
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    content = main_py.read_text(encoding="utf-8")

    assert '@app.post("/api/auth/register"' in content
    assert '@app.post("/api/auth/login")' in content
    assert '@app.get("/api/auth/me")' in content


def test_tenant_guard_is_present() -> None:
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    content = main_py.read_text(encoding="utf-8")
    assert "auth.assert_session_owner" in content
