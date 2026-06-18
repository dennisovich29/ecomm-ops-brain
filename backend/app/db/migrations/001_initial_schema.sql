-- Initial schema for AI E-commerce Operations Brain
-- Run via: alembic upgrade head

CREATE TABLE IF NOT EXISTS incidents (
    id          VARCHAR(36) PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query       TEXT NOT NULL,
    root_cause  TEXT,
    domains     TEXT[],
    confidence  FLOAT,
    embedding_id VARCHAR(128),
    resolved    BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS incident_actions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id VARCHAR(36) REFERENCES incidents(id),
    action_type VARCHAR(64),
    parameters  TEXT,
    approved    BOOLEAN,
    executed_at TIMESTAMPTZ,
    outcome     TEXT
);

CREATE TABLE IF NOT EXISTS daily_sales (
    date            DATE PRIMARY KEY,
    revenue         NUMERIC(12,2),
    order_count     INT,
    avg_order_value NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS products (
    id       VARCHAR(32) PRIMARY KEY,
    name     TEXT,
    category TEXT,
    price    NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS inventory (
    product_id  VARCHAR(32) REFERENCES products(id),
    date        DATE,
    stock_level INT,
    PRIMARY KEY (product_id, date)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id           VARCHAR(32) PRIMARY KEY,
    name         TEXT,
    channel      VARCHAR(32),
    status       VARCHAR(16),
    daily_budget NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category   VARCHAR(64),
    sentiment  VARCHAR(16),
    resolved   BOOLEAN DEFAULT FALSE
);
