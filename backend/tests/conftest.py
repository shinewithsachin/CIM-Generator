"""
Shared pytest fixtures. Env vars are set at import time, before `main`/`config`
are imported anywhere else in the test session, so every setting (DB path,
upload/output/chroma dirs, secrets, rate limiting) points at an isolated
temp sandbox instead of the developer's real local state.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

_TEST_DIR = Path(tempfile.mkdtemp(prefix="cim_test_"))
os.environ["DB_PATH"] = str(_TEST_DIR / "test_users.db")
os.environ["UPLOAD_DIR"] = str(_TEST_DIR / "uploads")
os.environ["OUTPUT_DIR"] = str(_TEST_DIR / "outputs")
os.environ["CHROMA_PERSIST_DIR"] = str(_TEST_DIR / "chroma_db")
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-not-for-production"
os.environ["APP_ENCRYPTION_KEY"] = "test-encryption-key-not-for-production"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
os.environ["DISABLE_RATE_LIMIT"] = "1"  # avoid cross-test flakiness; lockout logic is tested independently

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import database as db  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    db.init_db()
    yield


class _FakeEmbeddings:
    """Deterministic, dependency-free stand-in for HuggingFaceEmbeddings.

    Avoids downloading/loading a real (multi-GB) embedding model in tests —
    RAG correctness at the retrieval-scoring level isn't what these tests
    are asserting; the pipeline wiring is.
    """

    def __init__(self, *args, **kwargs):
        pass

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)

    @staticmethod
    def _vec(text: str):
        import hashlib

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:16]]


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    import rag_service

    monkeypatch.setattr(rag_service, "HuggingFaceEmbeddings", _FakeEmbeddings)
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def register_and_login(client: TestClient):
    """Returns a callable: () -> (auth_headers, email, user_id)."""

    def _make(password: str = "StrongPass123!"):
        email = f"user_{uuid.uuid4().hex[:10]}@example.com"
        reg = client.post(
            "/api/auth/register",
            json={"email": email, "name": "Test User", "password": password},
        )
        assert reg.status_code == 201, reg.text
        user_id = reg.json()["user"]["id"]

        login = client.post("/api/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        token = login.json()["token"]

        return {"Authorization": f"Bearer {token}"}, email, user_id

    return _make
