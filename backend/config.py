from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    # LLM Configuration (user-configurable at runtime)
    llm_provider: str = "auto"            # auto | openai | anthropic | groq
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Runtime-mutable config (updated via API)
_runtime_config: dict = {
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

def get_runtime_config() -> dict:
    return _runtime_config.copy()

def update_runtime_config(updates: dict) -> dict:
    _runtime_config.update(updates)
    return _runtime_config.copy()

def ensure_dirs():
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
