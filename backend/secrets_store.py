"""
Auto-generates and persists local secrets (JWT signing key, file-encryption key)
when not supplied via environment variables, so they stay stable across restarts
without forcing a manual setup step. Values persisted here are gitignored and
should be set explicitly via env vars in any real deployment.
"""
import logging
import os
import secrets

logger = logging.getLogger("cim.secrets")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_or_create_secret(env_value: str, filename: str, label: str, byte_length: int = 48) -> str:
    if env_value:
        return env_value

    path = os.path.join(_BASE_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read().strip()
        if existing:
            return existing

    generated = secrets.token_urlsafe(byte_length)
    with open(path, "w", encoding="utf-8") as f:
        f.write(generated)
    logger.warning(
        "%s not set via environment — generated and persisted to %s. "
        "Set it explicitly via env var for any real deployment.",
        label, path,
    )
    return generated
