"""
RAG service using ChromaDB + sentence-transformers.
Session-aware: each session gets its own Chroma collection.
"""
import os
import asyncio
from typing import List, Optional
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config import settings
from db.pgvector_store import PgVectorStore


class RAGService:
    def __init__(self, session_id: str, tenant_id: str, embedding_model: Optional[str] = None):
        if not tenant_id:
            raise ValueError("tenant_id is required for strict data isolation")

        self.session_id = session_id
        self.tenant_id = tenant_id
        self.collection_name = f"cim_{session_id.replace('-', '_')}"
        model_name = embedding_model or settings.embedding_model
        self.vector_backend = settings.vector_backend.lower().strip()

        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        if self.vector_backend == "pgvector":
            if not settings.postgres_dsn:
                raise ValueError("postgres_dsn is required when vector_backend='pgvector'")
            self.pgvector_store = PgVectorStore(
                dsn=settings.postgres_dsn,
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                embedding_model=model_name,
            )
            self.vectorstore = None
        else:
            self.vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=settings.chroma_persist_dir,
            )
            self.pgvector_store = None

    async def add_documents_async(self, docs: List[Document], source: str = "") -> None:
        """Add documents to the configured vector backend."""
        if not docs:
            return

        for doc in docs:
            doc.metadata.setdefault("source", source)
            doc.metadata["tenant_id"] = self.tenant_id
            doc.metadata["session_id"] = self.session_id

        if self.vector_backend == "pgvector" and self.pgvector_store is not None:
            await self.pgvector_store.add_documents(docs, source=source)
            return

        self.vectorstore.add_documents(docs)

    def add_documents(self, docs: List[Document], source: str = "") -> None:
        """Add documents to the vector store."""
        if not docs:
            return

        is_async_context = False
        try:
            asyncio.get_running_loop()
            is_async_context = True
        except RuntimeError:
            is_async_context = False

        if is_async_context:
            raise RuntimeError("Use add_documents_async inside async context")

        asyncio.run(self.add_documents_async(docs, source=source))

    async def retrieve_async(self, query: str, k: int = None) -> List[Document]:
        """Retrieve top-k relevant documents for a query."""
        k = k or settings.retrieval_k
        try:
            if self.vector_backend == "pgvector" and self.pgvector_store is not None:
                return await self.pgvector_store.similarity_search(query, k=k)

            return self.vectorstore.similarity_search(
                query,
                k=k,
                filter={"tenant_id": self.tenant_id, "session_id": self.session_id},
            )
        except Exception:
            return []

    def retrieve(self, query: str, k: int = None) -> List[Document]:
        is_async_context = False
        try:
            asyncio.get_running_loop()
            is_async_context = True
        except RuntimeError:
            is_async_context = False

        if is_async_context:
            raise RuntimeError("Use retrieve_async inside async context")

        return asyncio.run(self.retrieve_async(query, k=k))

    def retrieve_with_scores(self, query: str, k: int = None) -> List[tuple]:
        k = k or settings.retrieval_k
        try:
            if self.vector_backend == "pgvector" and self.pgvector_store is not None:
                docs = asyncio.run(self.pgvector_store.similarity_search(query, k=k))
                return [(doc, 0.0) for doc in docs]

            return self.vectorstore.similarity_search_with_score(
                query,
                k=k,
                filter={"tenant_id": self.tenant_id, "session_id": self.session_id},
            )
        except Exception:
            return []

    async def get_context_async(self, query: str, k: int = None, max_chars: int = 12000) -> str:
        """Retrieve and format context as a single string."""
        docs = await self.retrieve_async(query, k=k)
        parts = []
        total = 0
        for doc in docs:
            src = doc.metadata.get("source", "unknown")
            chunk = f"[Source: {src}]\n{doc.page_content}"
            if total + len(chunk) > max_chars:
                break
            parts.append(chunk)
            total += len(chunk)
        return "\n\n---\n\n".join(parts)

    def get_context(self, query: str, k: int = None, max_chars: int = 12000) -> str:
        is_async_context = False
        try:
            asyncio.get_running_loop()
            is_async_context = True
        except RuntimeError:
            is_async_context = False

        if is_async_context:
            raise RuntimeError("Use get_context_async inside async context")

        return asyncio.run(self.get_context_async(query, k=k, max_chars=max_chars))

    async def get_all_context_async(self, queries: List[str], max_chars: int = 15000) -> str:
        """Retrieve context for multiple related queries, deduplicated."""
        seen = set()
        parts = []
        total = 0
        for query in queries:
            docs = await self.retrieve_async(query, k=6)
            for doc in docs:
                key = doc.page_content[:100]
                if key in seen:
                    continue
                seen.add(key)
                src = doc.metadata.get("source", "unknown")
                chunk = f"[Source: {src}]\n{doc.page_content}"
                if total + len(chunk) > max_chars:
                    return "\n\n---\n\n".join(parts)
                parts.append(chunk)
                total += len(chunk)
        return "\n\n---\n\n".join(parts)

    def get_all_context(self, queries: List[str], max_chars: int = 15000) -> str:
        is_async_context = False
        try:
            asyncio.get_running_loop()
            is_async_context = True
        except RuntimeError:
            is_async_context = False

        if is_async_context:
            raise RuntimeError("Use get_all_context_async inside async context")

        return asyncio.run(self.get_all_context_async(queries, max_chars=max_chars))

    def delete_collection(self) -> None:
        try:
            self.vectorstore.delete_collection()
        except Exception:
            pass

    def document_count(self) -> int:
        try:
            return self.vectorstore._collection.count()
        except Exception:
            return 0
