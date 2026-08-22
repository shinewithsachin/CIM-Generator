from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # LLM Configuration (system-wide defaults; per-user overrides live in the DB, see user_config.py)
    llm_provider: str = "auto"            # auto | openai | anthropic | groq | demo
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"            # e.g. gpt-4o, claude-opus-4-7
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-latest"
    groq_model: str = "llama-3.3-70b-versatile"

    # Embedding model (runs locally, no API key needed)
    embedding_model: str = "BAAI/bge-m3"

    # Vector store
    vector_backend: str = "chroma"       # chroma | pgvector
    chroma_persist_dir: str = "./chroma_db"
    postgres_dsn: str = ""

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # RAG retrieval
    retrieval_k: int = 8

    # Paths
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"

    # Security
    jwt_secret_key: str = ""              # if empty, auto-generated + persisted to .secret_key
    app_encryption_key: str = ""          # if empty, auto-generated + persisted to .encryption_key
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_mb: int = 50
    retention_days: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

def get_allowed_origins() -> list[str]:
    return [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

def ensure_dirs():
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
