"""Tenant-isolated pgvector-backed retrieval with explicit tenant filters."""

from __future__ import annotations

import json
from typing import Iterable, List

import asyncpg
from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings


class PgVectorStore:
    def __init__(self, dsn: str, tenant_id: str, session_id: str, embedding_model: str) -> None:
        self.dsn = dsn
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    async def _conn(self) -> asyncpg.Connection:
        conn = await asyncpg.connect(self.dsn)
        # Critical for RLS: every connection must set request tenant context.
        await conn.execute("SELECT set_config('app.current_tenant', $1, true)", self.tenant_id)
        return conn

    async def add_documents(self, docs: Iterable[Document], source: str = "") -> None:
        docs = list(docs)
        if not docs:
            return

        texts = [doc.page_content for doc in docs]
        embeddings = self.embeddings.embed_documents(texts)

        conn = await self._conn()
        try:
            for idx, (doc, vec) in enumerate(zip(docs, embeddings)):
                merged_meta = {"source": source or doc.metadata.get("source", "unknown"), **doc.metadata}
                await conn.execute(
                    """
                    INSERT INTO tenant_documents
                    (tenant_id, session_id, source, chunk_index, content, embedding)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::vector)
                    """,
                    self.tenant_id,
                    self.session_id,
                    merged_meta.get("source", "unknown"),
                    idx,
                    doc.page_content,
                    json.dumps(vec),
                )
        finally:
            await conn.close()

    async def delete_session(self) -> None:
        conn = await self._conn()
        try:
            await conn.execute(
                "DELETE FROM tenant_documents WHERE tenant_id = $1::uuid AND session_id = $2::uuid",
                self.tenant_id,
                self.session_id,
            )
        finally:
            await conn.close()

    async def similarity_search(self, query: str, k: int) -> List[Document]:
        query_embedding = self.embeddings.embed_query(query)

        conn = await self._conn()
        try:
            rows = await conn.fetch(
                """
                SELECT source, chunk_index, content
                FROM tenant_documents
                WHERE tenant_id = $1::uuid
                  AND session_id = $2::uuid
                ORDER BY embedding <=> $3::vector
                LIMIT $4
                """,
                self.tenant_id,
                self.session_id,
                json.dumps(query_embedding),
                k,
            )
        finally:
            await conn.close()

        return [
            Document(
                page_content=row["content"],
                metadata={
                    "source": row["source"],
                    "chunk": row["chunk_index"],
                    "tenant_id": self.tenant_id,
                    "session_id": self.session_id,
                },
            )
            for row in rows
        ]
