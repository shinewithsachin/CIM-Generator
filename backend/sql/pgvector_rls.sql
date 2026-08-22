-- PostgreSQL + pgvector schema with strict tenant-level RLS isolation

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tenant_documents (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    session_id UUID NOT NULL,
    source TEXT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_documents_tenant_session
    ON tenant_documents (tenant_id, session_id);

CREATE INDEX IF NOT EXISTS idx_tenant_documents_embedding_ivfflat
    ON tenant_documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

ALTER TABLE tenant_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_documents FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_policy ON tenant_documents;
CREATE POLICY tenant_isolation_policy
    ON tenant_documents
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- For every DB request, set tenant context before queries:
-- SELECT set_config('app.current_tenant', '<tenant-uuid>', true);
