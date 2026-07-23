CREATE TABLE IF NOT EXISTS proxy_checks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    proxy_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proxy_checks_user ON proxy_checks (user_id, created_at DESC);
