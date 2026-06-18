-- Migration 004: varied 30-day seed data so different dates return different scenarios
-- Overwrites daily_sales, product_daily_sales, regional_sales with realistic variation
-- Each week has a distinct pattern: normal → spike → recovery → promo event

-- ── Truncate and rebuild daily_sales with realistic variation ────────────────
DELETE FROM product_daily_sales
WHERE date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE;

DELETE FROM regional_sales
WHERE date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE;

DELETE FROM campaign_daily_metrics
WHERE date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE;

DELETE FROM channel_daily_performance
WHERE date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE;

DELETE FROM daily_sales
WHERE date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE;

-- ── daily_sales: 30-day history with variation ────────────────────────────────
INSERT INTO daily_sales (date, revenue, order_count, avg_order_value)
SELECT
    s.d::date,
    CAST(CASE
        WHEN s.d = CURRENT_DATE - 1  THEN 31525.00
        WHEN s.d = CURRENT_DATE - 2  THEN 39200.00
        WHEN s.d = CURRENT_DATE - 3  THEN 47800.00
        WHEN s.d = CURRENT_DATE - 4  THEN 49100.00
        WHEN s.d = CURRENT_DATE - 5  THEN 62300.00
        WHEN s.d = CURRENT_DATE - 6  THEN 58900.00
        WHEN s.d = CURRENT_DATE - 7  THEN 55400.00
        WHEN s.d = CURRENT_DATE - 8  THEN 47200.00
        WHEN s.d = CURRENT_DATE - 9  THEN 48900.00
        WHEN s.d = CURRENT_DATE - 10 THEN 45300.00
        WHEN s.d = CURRENT_DATE - 11 THEN 51200.00
        WHEN s.d = CURRENT_DATE - 12 THEN 49800.00
        WHEN s.d = CURRENT_DATE - 13 THEN 52100.00
        WHEN s.d = CURRENT_DATE - 14 THEN 48500.00
        WHEN s.d = CURRENT_DATE - 15 THEN 54300.00
        WHEN s.d = CURRENT_DATE - 16 THEN 56700.00
        WHEN s.d = CURRENT_DATE - 17 THEN 53800.00
        WHEN s.d = CURRENT_DATE - 18 THEN 57200.00
        WHEN s.d = CURRENT_DATE - 19 THEN 55600.00
        WHEN s.d = CURRENT_DATE - 20 THEN 59100.00
        WHEN s.d = CURRENT_DATE - 21 THEN 61200.00
        WHEN s.d = CURRENT_DATE - 22 THEN 52400.00
        WHEN s.d = CURRENT_DATE - 23 THEN 50100.00
        WHEN s.d = CURRENT_DATE - 24 THEN 48700.00
        WHEN s.d = CURRENT_DATE - 25 THEN 33200.00
        WHEN s.d = CURRENT_DATE - 26 THEN 36800.00
        WHEN s.d = CURRENT_DATE - 27 THEN 44500.00
        WHEN s.d = CURRENT_DATE - 28 THEN 47300.00
        WHEN s.d = CURRENT_DATE - 29 THEN 48100.00
        ELSE 48500.00
    END AS NUMERIC),
    CASE
        WHEN s.d = CURRENT_DATE - 1  THEN 230
        WHEN s.d = CURRENT_DATE - 2  THEN 275
        WHEN s.d = CURRENT_DATE - 5  THEN 420
        WHEN s.d = CURRENT_DATE - 6  THEN 395
        WHEN s.d = CURRENT_DATE - 25 THEN 245
        ELSE 320
    END,
    ROUND(CAST(CASE
        WHEN s.d = CURRENT_DATE - 1  THEN 137.07
        WHEN s.d = CURRENT_DATE - 5  THEN 148.33
        ELSE 151.56
    END AS NUMERIC), 2)
FROM generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval) AS s(d)
ON CONFLICT (date) DO UPDATE
    SET revenue         = EXCLUDED.revenue,
        order_count     = EXCLUDED.order_count,
        avg_order_value = EXCLUDED.avg_order_value;

-- ── Product daily sales: reflects stockout days ───────────────────────────────
INSERT INTO product_daily_sales (product_id, date, units_sold, revenue)
SELECT
    p.id AS product_id,
    d::date AS date,
    CASE
        -- yesterday: SKU-001/002/003 stocked out, SKU-004/005 pick up slack
        WHEN d = CURRENT_DATE - 1 AND p.id IN ('SKU-001','SKU-002','SKU-003') THEN 0
        WHEN d = CURRENT_DATE - 1 AND p.id = 'SKU-004' THEN 103
        WHEN d = CURRENT_DATE - 1 AND p.id = 'SKU-005' THEN 92
        -- day -25: another stockout event (SKU-001 only)
        WHEN d = CURRENT_DATE - 25 AND p.id = 'SKU-001' THEN 0
        WHEN d = CURRENT_DATE - 25 AND p.id = 'SKU-004' THEN 85
        -- promo days (day -5 to -6): fitness/footwear surge
        WHEN d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 AND p.id = 'SKU-002' THEN 145
        WHEN d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 AND p.id = 'SKU-003' THEN 120
        -- normal distribution
        WHEN p.id = 'SKU-001' THEN 96
        WHEN p.id = 'SKU-002' THEN 80
        WHEN p.id = 'SKU-003' THEN 64
        WHEN p.id = 'SKU-004' THEN 48
        WHEN p.id = 'SKU-005' THEN 32
        ELSE 0
    END,
    CASE
        WHEN d = CURRENT_DATE - 1 AND p.id IN ('SKU-001','SKU-002','SKU-003') THEN 0
        WHEN d = CURRENT_DATE - 1 AND p.id = 'SKU-004' THEN 14186.25
        WHEN d = CURRENT_DATE - 1 AND p.id = 'SKU-005' THEN 12610.00
        WHEN d = CURRENT_DATE - 25 AND p.id = 'SKU-001' THEN 0
        WHEN d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 AND p.id = 'SKU-002' THEN 10873.55
        WHEN d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 AND p.id = 'SKU-003' THEN 5998.80
        WHEN p.id = 'SKU-001' THEN 14550.00
        WHEN p.id = 'SKU-002' THEN 12125.00
        WHEN p.id = 'SKU-003' THEN 9700.00
        WHEN p.id = 'SKU-004' THEN 7275.00
        WHEN p.id = 'SKU-005' THEN 4850.00
        ELSE 0
    END
FROM products p,
     generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval) AS d
ON CONFLICT (product_id, date) DO UPDATE
    SET units_sold = EXCLUDED.units_sold,
        revenue    = EXCLUDED.revenue;

-- ── Regional sales rebuilt ────────────────────────────────────────────────────
INSERT INTO regional_sales (region, date, revenue, order_count)
SELECT
    r.region,
    ds.date,
    ROUND(ds.revenue * CAST(r.share AS NUMERIC), 2),
    ROUND(CAST(ds.order_count AS NUMERIC) * CAST(r.share AS NUMERIC))::int
FROM daily_sales ds
CROSS JOIN (VALUES
    ('North America', 0.50),
    ('Europe',        0.30),
    ('Asia Pacific',  0.15),
    ('Rest of World', 0.05)
) AS r(region, share)
WHERE ds.date BETWEEN CURRENT_DATE - 29 AND CURRENT_DATE
ON CONFLICT (region, date) DO UPDATE
    SET revenue     = EXCLUDED.revenue,
        order_count = EXCLUDED.order_count;

-- ── Campaign metrics: CAMP-001 was also paused on day -25 ─────────────────────
INSERT INTO campaign_daily_metrics (campaign_id, date, spend, impressions, clicks, conversions, revenue)
SELECT
    c.id,
    d::date,
    CASE
        WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
        WHEN c.id = 'CAMP-001' THEN 850.00
        WHEN c.id = 'CAMP-002' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 180.00
        WHEN c.id = 'CAMP-002' THEN 120.00
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
        WHEN c.id = 'CAMP-001' THEN 42000
        WHEN c.id = 'CAMP-002' THEN 18000
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
        WHEN c.id = 'CAMP-001' THEN 1260
        WHEN c.id = 'CAMP-002' THEN 540
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
        WHEN c.id = 'CAMP-001' THEN 95
        WHEN c.id = 'CAMP-002' THEN 38
        ELSE 0
    END,
    CASE
        WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
        WHEN c.id = 'CAMP-001' THEN 3570.00
        WHEN c.id = 'CAMP-002' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 2100.00
        WHEN c.id = 'CAMP-002' THEN 1180.00
        ELSE 0
    END
FROM campaigns c,
     generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval) AS d
ON CONFLICT (campaign_id, date) DO UPDATE
    SET spend       = EXCLUDED.spend,
        impressions = EXCLUDED.impressions,
        clicks      = EXCLUDED.clicks,
        conversions = EXCLUDED.conversions,
        revenue     = EXCLUDED.revenue;

-- ── Channel performance ───────────────────────────────────────────────────────
INSERT INTO channel_daily_performance (channel, date, spend, revenue)
SELECT channel, d::date, spend, revenue FROM (
    SELECT
        c.channel, d,
        CASE
            WHEN c.channel = 'paid_search' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
            WHEN c.channel = 'paid_search' THEN 850.00
            WHEN c.channel = 'email' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 180.00
            WHEN c.channel = 'email' THEN 120.00
            ELSE 0
        END AS spend,
        CASE
            WHEN c.channel = 'paid_search' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
            WHEN c.channel = 'paid_search' THEN 3570.00
            WHEN c.channel = 'email' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 2100.00
            WHEN c.channel = 'email' THEN 1280.00
            WHEN c.channel = 'organic' AND d = CURRENT_DATE - 1 THEN 5200.00
            WHEN c.channel = 'organic' THEN 6650.00
            ELSE 0
        END AS revenue
    FROM (VALUES ('paid_search'), ('email'), ('organic')) AS c(channel),
         generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval) AS d
) sub
ON CONFLICT (channel, date) DO UPDATE
    SET spend   = EXCLUDED.spend,
        revenue = EXCLUDED.revenue;

-- ── Inventory: add historical stock snapshots ─────────────────────────────────
-- Today's stock is already set - add a few historical snapshots to show trend
INSERT INTO inventory (product_id, date, stock_level, reorder_point)
VALUES
    -- 5 days ago: all in stock
    ('SKU-001', CURRENT_DATE - 5, 280, 50),
    ('SKU-002', CURRENT_DATE - 5, 210, 50),
    ('SKU-003', CURRENT_DATE - 5, 175, 50),
    ('SKU-004', CURRENT_DATE - 5, 60,  20),
    ('SKU-005', CURRENT_DATE - 5, 250, 30),
    -- day -25: SKU-001 was out that day too
    ('SKU-001', CURRENT_DATE - 25, 0,   50),
    ('SKU-002', CURRENT_DATE - 25, 180, 50),
    ('SKU-003', CURRENT_DATE - 25, 140, 50),
    ('SKU-004', CURRENT_DATE - 25, 45,  20),
    ('SKU-005', CURRENT_DATE - 25, 250, 30)
ON CONFLICT (product_id, date) DO NOTHING;

-- ── More realistic support tickets: spread across 30 days ─────────────────────
-- Delete old fixed tickets and insert varied ones
DELETE FROM support_tickets WHERE id::text LIKE 'a1b2c3d4%';

INSERT INTO support_tickets (created_at, category, sentiment, resolved) VALUES
    -- Yesterday: spike from stockouts
    (NOW() - interval '1 day',         'Out of stock / can''t purchase', 'negative', false),
    (NOW() - interval '1 day 1 hour',  'Out of stock / can''t purchase', 'negative', false),
    (NOW() - interval '1 day 2 hours', 'Out of stock / can''t purchase', 'negative', false),
    (NOW() - interval '1 day 3 hours', 'Out of stock / can''t purchase', 'negative', false),
    (NOW() - interval '1 day 4 hours', 'Out of stock / can''t purchase', 'negative', true),
    (NOW() - interval '1 day 5 hours', 'Order delayed / shipping issue', 'negative', false),
    (NOW() - interval '1 day 6 hours', 'Order delayed / shipping issue', 'negative', false),
    (NOW() - interval '1 day 7 hours', 'Refund request',                 'negative', false),
    (NOW() - interval '1 day 8 hours', 'Refund request',                 'negative', true),
    (NOW() - interval '1 day 9 hours', 'General inquiry',                'neutral',  true),
    -- 2 days ago: recovering
    (NOW() - interval '2 days',        'Out of stock / can''t purchase', 'negative', true),
    (NOW() - interval '2 days 2 hours','Refund request',                 'negative', false),
    (NOW() - interval '2 days 4 hours','General inquiry',                'neutral',  true),
    -- 3-4 days ago: normal
    (NOW() - interval '3 days',        'General inquiry',                'neutral',  true),
    (NOW() - interval '3 days 3 hours','Product question',               'neutral',  true),
    (NOW() - interval '4 days',        'General inquiry',                'neutral',  true),
    (NOW() - interval '4 days 5 hours','Delivery update',                'neutral',  true),
    -- Promo days (5-6 days ago): mostly positive/neutral
    (NOW() - interval '5 days',        'Promo code inquiry',             'neutral',  true),
    (NOW() - interval '5 days 1 hour', 'Promo code inquiry',             'neutral',  true),
    (NOW() - interval '5 days 2 hours','General inquiry',                'neutral',  true),
    (NOW() - interval '6 days',        'Promo code inquiry',             'positive', true),
    (NOW() - interval '6 days 2 hours','Product question',               'neutral',  true),
    -- Day -25: previous stockout event
    (NOW() - interval '25 days',       'Out of stock / can''t purchase', 'negative', true),
    (NOW() - interval '25 days 1 hour','Out of stock / can''t purchase', 'negative', true),
    (NOW() - interval '25 days 2 hours','Refund request',                'negative', true),
    (NOW() - interval '25 days 3 hours','General inquiry',               'neutral',  true);
