"""
Symmetric encryption for data at rest: uploaded confidential documents and
stored per-user LLM API keys. Backed by a single Fernet key sourced from
APP_ENCRYPTION_KEY, auto-generated and persisted locally if unset (see
secrets_store.py) so behavior is identical to the JWT secret handling.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from config import settings
from secrets_store import get_or_create_secret

_key_material = get_or_create_secret(
    settings.app_encryption_key, ".encryption_key", "APP_ENCRYPTION_KEY", byte_length=32
)
# Fernet requires a 32-byte urlsafe-base64 key; token_urlsafe output isn't
# guaranteed valid base64 padding, so derive a proper Fernet key from it.
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(_key_material.encode()).digest()))


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet.decrypt(token)


def encrypt_text(value: str) -> str:
    if not value:
        return ""
    return _fernet.encrypt(value.encode()).decode()


def decrypt_text(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return ""
