-- Run this in Supabase: SQL Editor → New query → Run

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    pack_id TEXT NOT NULL,
    pack_name TEXT NOT NULL,
    proxy_count INTEGER NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    trx_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    proxies TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS proxy_stock (
    id SERIAL PRIMARY KEY,
    proxy_line TEXT NOT NULL UNIQUE,
    used BOOLEAN DEFAULT FALSE,
    order_id INTEGER REFERENCES orders(id),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proxy_stock_available ON proxy_stock (used, id) WHERE used = FALSE;
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);

INSERT INTO settings (key, value) VALUES ('maintenance', '0')
ON CONFLICT (key) DO NOTHING;
