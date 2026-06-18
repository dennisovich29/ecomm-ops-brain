-- Migration 003: extend schema for full v2 postgres repository support
-- Adds tables for product sales breakdown, regional sales, campaign metrics,
-- channel performance, promotions, and product views.

-- ── Product daily sales breakdown ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product_daily_sales (
    product_id  VARCHAR(32) REFERENCES products(id),
    date        DATE        NOT NULL,
    units_sold  INT         NOT NULL DEFAULT 0,
    revenue     NUMERIC(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, date)
);

-- ── Regional sales ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regional_sales (
    region      VARCHAR(64) NOT NULL,
    date        DATE        NOT NULL,
    revenue     NUMERIC(12,2) NOT NULL DEFAULT 0,
    order_count INT         NOT NULL DEFAULT 0,
    PRIMARY KEY (region, date)
);

-- ── Campaign daily metrics ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaign_daily_metrics (
    campaign_id  VARCHAR(32) REFERENCES campaigns(id),
    date         DATE        NOT NULL,
    spend        NUMERIC(10,2) NOT NULL DEFAULT 0,
    impressions  INT         NOT NULL DEFAULT 0,
    clicks       INT         NOT NULL DEFAULT 0,
    conversions  INT         NOT NULL DEFAULT 0,
    revenue      NUMERIC(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (campaign_id, date)
);

-- ── Channel daily performance ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS channel_daily_performance (
    channel     VARCHAR(32) NOT NULL,
    date        DATE        NOT NULL,
    spend       NUMERIC(10,2) NOT NULL DEFAULT 0,
    revenue     NUMERIC(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (channel, date)
);

-- ── Promotions ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promotions (
    id           VARCHAR(64) PRIMARY KEY,
    name         TEXT        NOT NULL,
    discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    products     TEXT[]      NOT NULL DEFAULT '{}',
    status       VARCHAR(16) NOT NULL DEFAULT 'scheduled',
    scheduled_at TIMESTAMPTZ
);

-- Widen id column if table was previously created with VARCHAR(32)
ALTER TABLE promotions ALTER COLUMN id TYPE VARCHAR(64);

-- ── Product views (for views-vs-purchases) ────────────────────────────────
CREATE TABLE IF NOT EXISTS product_views (
    product_id  VARCHAR(32) REFERENCES products(id),
    date        DATE        NOT NULL,
    views       INT         NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, date)
);

-- ── Inventory with reorder point ──────────────────────────────────────────
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS reorder_point INT NOT NULL DEFAULT 50;

-- ── Seed extended data ────────────────────────────────────────────────────

-- Product daily sales: yesterday is a bad day (top 3 SKUs out of stock)
INSERT INTO product_daily_sales (product_id, date, units_sold, revenue)
SELECT
    p.product_id,
    s.d,
    CASE
        WHEN s.d = CURRENT_DATE - 1 AND p.product_id IN ('SKU-001','SKU-002','SKU-003') THEN 0
        WHEN p.product_id = 'SKU-001' THEN 96
        WHEN p.product_id = 'SKU-002' THEN 80
        WHEN p.product_id = 'SKU-003' THEN 64
        WHEN p.product_id = 'SKU-004' THEN CASE WHEN s.d = CURRENT_DATE - 1 THEN 103 ELSE 48 END
        WHEN p.product_id = 'SKU-005' THEN CASE WHEN s.d = CURRENT_DATE - 1 THEN 92  ELSE 32 END
        ELSE 0
    END,
    CASE
        WHEN s.d = CURRENT_DATE - 1 AND p.product_id IN ('SKU-001','SKU-002','SKU-003') THEN 0
        WHEN p.product_id = 'SKU-001' THEN CASE WHEN s.d = CURRENT_DATE - 1 THEN 0 ELSE 14550.00 END
        WHEN p.product_id = 'SKU-002' THEN CASE WHEN s.d = CURRENT_DATE - 1 THEN 0 ELSE 12125.00 END
        WHEN p.product_id = 'SKU-003' THEN CASE WHEN s.d = CURRENT_DATE - 1 THEN 0 ELSE 9700.00  END
        WHEN p.product_id = 'SKU-004' THEN CASE WHEN s.d = CURRENT_DATE - 1 THEN 14186.25 ELSE 7275.00 END
        WHEN p.product_id = 'SKU-005' THEN CASE WHEN s.d = CURRENT_DATE - 1 THEN 12610.00 ELSE 4850.00 END
        ELSE 0
    END
FROM
    (SELECT id AS product_id FROM products) p,
    (SELECT generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval)::date AS d) s
ON CONFLICT (product_id, date) DO NOTHING;

-- Regional sales
INSERT INTO regional_sales (region, date, revenue, order_count)
SELECT
    r.region,
    s.d,
    ROUND(ds.revenue * r.share, 2),
    ROUND(ds.order_count * r.share)::int
FROM
    daily_sales ds,
    (SELECT generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval)::date AS d) s,
    (VALUES
        ('North America', 0.50),
        ('Europe',        0.30),
        ('Asia Pacific',  0.15),
        ('Rest of World', 0.05)
    ) AS r(region, share)
WHERE ds.date = s.d
ON CONFLICT (region, date) DO NOTHING;

-- Campaign daily metrics: CAMP-001 was paused yesterday
INSERT INTO campaign_daily_metrics (campaign_id, date, spend, impressions, clicks, conversions, revenue)
SELECT
    c.id,
    s.d,
    CASE
        WHEN c.id = 'CAMP-001' AND s.d = CURRENT_DATE - 1 THEN 0
        WHEN c.id = 'CAMP-001' THEN 850.00
        WHEN c.id = 'CAMP-002' THEN 120.00
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND s.d = CURRENT_DATE - 1 THEN 0
        WHEN c.id = 'CAMP-001' THEN 42000
        WHEN c.id = 'CAMP-002' THEN 18000
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND s.d = CURRENT_DATE - 1 THEN 0
        WHEN c.id = 'CAMP-001' THEN 1260
        WHEN c.id = 'CAMP-002' THEN 540
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND s.d = CURRENT_DATE - 1 THEN 0
        WHEN c.id = 'CAMP-001' THEN 95
        WHEN c.id = 'CAMP-002' THEN 38
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND s.d = CURRENT_DATE - 1 THEN 0
        WHEN c.id = 'CAMP-001' THEN 3570.00
        WHEN c.id = 'CAMP-002' THEN 1180.00
        ELSE 0
    END
FROM campaigns c,
     (SELECT generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval)::date AS d) s
ON CONFLICT (campaign_id, date) DO NOTHING;

-- Channel daily performance
INSERT INTO channel_daily_performance (channel, date, spend, revenue)
SELECT channel, d, spend, revenue FROM (
    VALUES
        ('paid_search', CURRENT_DATE - 1, 0.00,   0.00),
        ('email',       CURRENT_DATE - 1, 120.00, 1180.00),
        ('organic',     CURRENT_DATE - 1, 0.00,   5200.00)
) AS v(channel, d, spend, revenue)
ON CONFLICT (channel, date) DO NOTHING;

-- Seed 30 days of channel data (non-bad days)
INSERT INTO channel_daily_performance (channel, date, spend, revenue)
SELECT channel, d, spend, revenue FROM (
    SELECT
        c.channel,
        s.d,
        c.spend,
        c.revenue
    FROM (VALUES
        ('paid_search', 850.00,  3570.00),
        ('email',       120.00,  1280.00),
        ('organic',     0.00,    6650.00)
    ) AS c(channel, spend, revenue),
    (SELECT generate_series(CURRENT_DATE - 29, CURRENT_DATE - 2, '1 day'::interval)::date AS d) s
) sub
ON CONFLICT (channel, date) DO NOTHING;

-- Promotions
INSERT INTO promotions (id, name, discount_pct, products, status, scheduled_at) VALUES
    ('PROMO-001', 'Summer Sale — 15% off Fitness', 15.0, ARRAY['SKU-003'], 'missed',
     (CURRENT_DATE - 1)::timestamptz + interval '8 hours')
ON CONFLICT (id) DO NOTHING;

-- Product views
INSERT INTO product_views (product_id, date, views)
VALUES
    ('SKU-001', CURRENT_DATE - 1, 1800),
    ('SKU-002', CURRENT_DATE - 1, 1200),
    ('SKU-003', CURRENT_DATE - 1, 900),
    ('SKU-004', CURRENT_DATE - 1, 400),
    ('SKU-005', CURRENT_DATE - 1, 300)
ON CONFLICT (product_id, date) DO NOTHING;

-- Update inventory with reorder points
UPDATE inventory SET reorder_point = 50  WHERE product_id IN ('SKU-001','SKU-002','SKU-003');
UPDATE inventory SET reorder_point = 20  WHERE product_id = 'SKU-004';
UPDATE inventory SET reorder_point = 30  WHERE product_id = 'SKU-005';
