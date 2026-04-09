
CREATE TABLE IF NOT EXISTS ingestion_audit (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    document_name VARCHAR(255) NOT NULL,
    chunk_count INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message TEXT,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prompt_registry (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    prompt_text TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    avg_feedback_score FLOAT DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (tenant_id, version)
);

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating IN (1, -1)),
    prompt_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_tenant ON ingestion_audit(tenant_id);
CREATE INDEX IF NOT EXISTS idx_prompt_tenant_active ON prompt_registry(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON feedback(tenant_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(tenant_id, rating);