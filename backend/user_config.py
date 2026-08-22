"""
Per-user LLM configuration, backed by SQLite (see database.user_llm_config).

Replaces the old process-wide global config dict, which leaked one user's
provider/API-key choice to every other concurrent user. Each user's saved
config overlays the system-wide Settings defaults; API keys are stored
Fernet-encrypted at rest (see encryption.py).
"""
from typing import Any, Dict

import database as db
import encryption
from config import settings

_ENCRYPTED_FIELDS = {"openai_api_key", "anthropic_api_key", "groq_api_key"}

_ALLOWED_FIELDS = {
    "llm_provider", "llm_model",
    "openai_api_key", "anthropic_api_key", "groq_api_key",
    "openai_model", "anthropic_model", "groq_model",
    "embedding_model", "vector_backend", "postgres_dsn",
}


def _defaults() -> Dict[str, Any]:
    return {
        "llm_provider": settings.llm_provider,
        "llm_api_key": settings.llm_api_key,
        "llm_model": settings.llm_model,
        "openai_api_key": settings.openai_api_key,
        "anthropic_api_key": settings.anthropic_api_key,
        "groq_api_key": settings.groq_api_key,
        "openai_model": settings.openai_model,
        "anthropic_model": settings.anthropic_model,
        "groq_model": settings.groq_model,
        "embedding_model": settings.embedding_model,
        "vector_backend": settings.vector_backend,
        "postgres_dsn": settings.postgres_dsn,
    }


def get_user_config(user_id: str) -> Dict[str, Any]:
    cfg = _defaults()
    row = db.get_user_llm_config_row(user_id)
    if not row:
        return cfg

    for field in ("llm_provider", "llm_model", "openai_model", "anthropic_model",
                  "groq_model", "embedding_model", "vector_backend", "postgres_dsn"):
        if row.get(field):
            cfg[field] = row[field]

    for field in _ENCRYPTED_FIELDS:
        enc_val = row.get(f"{field}_enc")
        if enc_val:
            cfg[field] = encryption.decrypt_text(enc_val)

    return cfg


def set_user_config(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    filtered = {k: v for k, v in updates.items() if k in _ALLOWED_FIELDS and v is not None}
    db_fields: Dict[str, Any] = {}
    for key, value in filtered.items():
        if key in _ENCRYPTED_FIELDS:
            db_fields[f"{key}_enc"] = encryption.encrypt_text(value)
        else:
            db_fields[key] = value

    if db_fields:
        db.upsert_user_llm_config(user_id, db_fields)

    return get_user_config(user_id)
