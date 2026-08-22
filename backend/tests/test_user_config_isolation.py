"""
Regression test for the bug found in the pre-hardening audit: LLM config
used to live in a single process-wide dict (config.get_runtime_config()),
so one user's saved provider/API key silently applied to every other
concurrent user. Config is now per-user (user_config.py, backed by
database.user_llm_config) — this asserts that isolation actually holds.
"""
from fastapi.testclient import TestClient


def test_config_does_not_leak_across_users(client: TestClient, register_and_login) -> None:
    headers_a, _, _ = register_and_login()
    headers_b, _, _ = register_and_login()

    set_a = client.put(
        "/api/config",
        headers=headers_a,
        json={"llm_provider": "openai", "openai_api_key": "sk-secret-key-AAAA", "openai_model": "gpt-4o-mini"},
    )
    assert set_a.status_code == 200

    set_b = client.put(
        "/api/config",
        headers=headers_b,
        json={"llm_provider": "anthropic", "anthropic_api_key": "sk-secret-key-BBBB", "anthropic_model": "claude-3-5-sonnet-latest"},
    )
    assert set_b.status_code == 200

    cfg_a = client.get("/api/config", headers=headers_a).json()
    cfg_b = client.get("/api/config", headers=headers_b).json()

    assert cfg_a["llm_provider"] == "openai"
    assert cfg_b["llm_provider"] == "anthropic"

    # Each user only sees their own (masked) key, never the other's.
    assert cfg_a["openai_api_key"].endswith("AAAA")
    assert not cfg_b.get("openai_api_key")
    assert cfg_b["anthropic_api_key"].endswith("BBBB")
    assert not cfg_a.get("anthropic_api_key")


def test_unset_user_falls_back_to_system_defaults(client: TestClient, register_and_login) -> None:
    headers, _, _ = register_and_login()
    cfg = client.get("/api/config", headers=headers).json()
    # A brand-new user with no saved config gets the system-wide defaults,
    # not an error and not another user's settings.
    assert "llm_provider" in cfg
    assert "embedding_model" in cfg
