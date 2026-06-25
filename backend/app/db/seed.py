from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.postgres import get_engine

_log = logging.getLogger(__name__)


async def seed_data() -> None:
    """Seed all operational data. Skips if products already exist (volume has data)."""
    engine = get_engine()
    async with engine.begin() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM products"))).scalar()
        if count and count > 0:
            _log.info("Seed skipped — data already present (%d products)", count)
            return

    _log.info("Seeding database...")
    async with engine.begin() as conn:
        # ── Reference data ────────────────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO products (id, name, category, price) VALUES
                ('SKU-001', 'Wireless Headphones Pro', 'Electronics', 89.99),
                ('SKU-002', 'Running Shoes X2',        'Footwear',    74.99),
                ('SKU-003', 'Yoga Mat Premium',        'Fitness',     49.99),
                ('SKU-004', 'Coffee Grinder 500',      'Kitchen',     39.99),
                ('SKU-005', 'Laptop Stand Foldable',   'Electronics', 34.99)
            ON CONFLICT (id) DO NOTHING
        """))

        await conn.execute(text("""
            INSERT INTO campaigns (id, name, channel, status, daily_budget) VALUES
                ('CAMP-001', 'Google Shopping — Electronics', 'paid_search', 'paused', 850.00),
                ('CAMP-002', 'Email — Weekly Deals',           'email',       'active', 120.00)
            ON CONFLICT (id) DO NOTHING
        """))

        await conn.execute(text("""
            INSERT INTO promotions (id, name, discount_pct, products, status, scheduled_at) VALUES
                ('PROMO-001', 'Summer Sale — 15% off Fitness', 15.0, ARRAY['SKU-003'], 'missed',
                 (CURRENT_DATE - 1)::timestamptz + interval '8 hours')
            ON CONFLICT (id) DO NOTHING
        """))

        # ── Incidents & actions ───────────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO incidents (id, created_at, query, root_cause, domains, confidence, resolved) VALUES
                ('INC-2024-001', NOW() - interval '1 day 2 hours',
                 'Why did revenue drop 35% yesterday?',
                 'Simultaneous stockouts on top 3 SKUs (SKU-001, SKU-002, SKU-003) eliminated $15,000+ in potential revenue. Google Shopping campaign CAMP-001 was paused on the same day, compounding the organic traffic loss.',
                 ARRAY['sales', 'inventory', 'marketing'], 0.92, false),
                ('INC-2024-002', NOW() - interval '3 days',
                 'Support ticket volume spike — 130% above 7-day average',
                 'Delayed restock on SKU-003 (Yoga Mat Premium) caused a 48-hour stockout, generating 22 out-of-stock complaints and a secondary wave of refund requests.',
                 ARRAY['support', 'inventory'], 0.85, true)
            ON CONFLICT (id) DO NOTHING
        """))

        await conn.execute(text("""
            INSERT INTO incident_actions (id, incident_id, action_type, parameters, approved, executed_at, outcome) VALUES
                ('b2c3d4e5-0001-0001-0001-000000000001', 'INC-2024-001', 'restock_order',
                 '{"product_id": "SKU-001", "quantity": 500, "supplier": "primary", "priority": "urgent"}',
                 true, NOW() - interval '23 hours', 'Restock order placed. Estimated arrival 48-72 hours.'),
                ('b2c3d4e5-0001-0001-0001-000000000002', 'INC-2024-001', 'restock_order',
                 '{"product_id": "SKU-002", "quantity": 300, "supplier": "primary", "priority": "urgent"}',
                 true, NOW() - interval '23 hours', 'Restock order placed. Estimated arrival 48-72 hours.'),
                ('b2c3d4e5-0001-0001-0001-000000000003', 'INC-2024-001', 'restock_order',
                 '{"product_id": "SKU-003", "quantity": 200, "supplier": "primary", "priority": "urgent"}',
                 true, NOW() - interval '22 hours', 'Restock order placed. Estimated arrival 48-72 hours.'),
                ('b2c3d4e5-0001-0001-0001-000000000004', 'INC-2024-001', 'resume_campaign',
                 '{"campaign_id": "CAMP-001", "budget_adjustment": 0}',
                 false, null, null),
                ('b2c3d4e5-0001-0001-0002-000000000001', 'INC-2024-002', 'restock_order',
                 '{"product_id": "SKU-003", "quantity": 200, "supplier": "secondary", "priority": "standard"}',
                 true, NOW() - interval '3 days', 'Restock completed. Stock level restored to 200 units.')
            ON CONFLICT (id) DO NOTHING
        """))

        # ── Today's inventory snapshot ────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO inventory (product_id, date, stock_level, reorder_point) VALUES
                ('SKU-001', CURRENT_DATE,      0,   50),
                ('SKU-002', CURRENT_DATE,      0,   50),
                ('SKU-003', CURRENT_DATE,      0,   50),
                ('SKU-004', CURRENT_DATE,      12,  20),
                ('SKU-005', CURRENT_DATE,      250, 30),
                ('SKU-001', CURRENT_DATE - 5,  280, 50),
                ('SKU-002', CURRENT_DATE - 5,  210, 50),
                ('SKU-003', CURRENT_DATE - 5,  175, 50),
                ('SKU-004', CURRENT_DATE - 5,  60,  20),
                ('SKU-005', CURRENT_DATE - 5,  250, 30),
                ('SKU-001', CURRENT_DATE - 25, 0,   50),
                ('SKU-002', CURRENT_DATE - 25, 180, 50),
                ('SKU-003', CURRENT_DATE - 25, 140, 50),
                ('SKU-004', CURRENT_DATE - 25, 45,  20),
                ('SKU-005', CURRENT_DATE - 25, 250, 30)
            ON CONFLICT (product_id, date) DO NOTHING
        """))

        # ── 30-day daily_sales with realistic variation ───────────────────────
        await conn.execute(text("""
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
                    WHEN s.d = CURRENT_DATE - 1 THEN 137.07
                    WHEN s.d = CURRENT_DATE - 5 THEN 148.33
                    ELSE 151.56
                END AS NUMERIC), 2)
            FROM generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval) AS s(d)
            ON CONFLICT (date) DO NOTHING
        """))

        # ── Product daily sales ───────────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO product_daily_sales (product_id, date, units_sold, revenue)
            SELECT
                p.id, d::date,
                CASE
                    WHEN d = CURRENT_DATE - 1  AND p.id IN ('SKU-001','SKU-002','SKU-003') THEN 0
                    WHEN d = CURRENT_DATE - 1  AND p.id = 'SKU-004' THEN 103
                    WHEN d = CURRENT_DATE - 1  AND p.id = 'SKU-005' THEN 92
                    WHEN d = CURRENT_DATE - 25 AND p.id = 'SKU-001' THEN 0
                    WHEN d = CURRENT_DATE - 25 AND p.id = 'SKU-004' THEN 85
                    WHEN d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 AND p.id = 'SKU-002' THEN 145
                    WHEN d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 AND p.id = 'SKU-003' THEN 120
                    WHEN p.id = 'SKU-001' THEN 96
                    WHEN p.id = 'SKU-002' THEN 80
                    WHEN p.id = 'SKU-003' THEN 64
                    WHEN p.id = 'SKU-004' THEN 48
                    WHEN p.id = 'SKU-005' THEN 32
                    ELSE 0
                END,
                CASE
                    WHEN d = CURRENT_DATE - 1  AND p.id IN ('SKU-001','SKU-002','SKU-003') THEN 0
                    WHEN d = CURRENT_DATE - 1  AND p.id = 'SKU-004' THEN 14186.25
                    WHEN d = CURRENT_DATE - 1  AND p.id = 'SKU-005' THEN 12610.00
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
            ON CONFLICT (product_id, date) DO NOTHING
        """))

        # ── Regional sales ────────────────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO regional_sales (region, date, revenue, order_count)
            SELECT
                r.region, ds.date,
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
            ON CONFLICT (region, date) DO NOTHING
        """))

        # ── Campaign daily metrics ────────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO campaign_daily_metrics (campaign_id, date, spend, impressions, clicks, conversions, revenue)
            SELECT
                c.id, d::date,
                CASE
                    WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
                    WHEN c.id = 'CAMP-001' THEN 850.00
                    WHEN c.id = 'CAMP-002' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 180.00
                    WHEN c.id = 'CAMP-002' THEN 120.00 ELSE 0
                END,
                CASE
                    WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
                    WHEN c.id = 'CAMP-001' THEN 42000 WHEN c.id = 'CAMP-002' THEN 18000 ELSE 0
                END,
                CASE
                    WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
                    WHEN c.id = 'CAMP-001' THEN 1260 WHEN c.id = 'CAMP-002' THEN 540 ELSE 0
                END,
                CASE
                    WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
                    WHEN c.id = 'CAMP-001' THEN 95 WHEN c.id = 'CAMP-002' THEN 38 ELSE 0
                END,
                CASE
                    WHEN c.id = 'CAMP-001' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
                    WHEN c.id = 'CAMP-001' THEN 3570.00
                    WHEN c.id = 'CAMP-002' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 2100.00
                    WHEN c.id = 'CAMP-002' THEN 1180.00 ELSE 0
                END
            FROM campaigns c,
                 generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval) AS d
            ON CONFLICT (campaign_id, date) DO NOTHING
        """))

        # ── Channel daily performance ─────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO channel_daily_performance (channel, date, spend, revenue)
            SELECT c.channel, d::date,
                CASE
                    WHEN c.channel = 'paid_search' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
                    WHEN c.channel = 'paid_search' THEN 850.00
                    WHEN c.channel = 'email' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 180.00
                    WHEN c.channel = 'email' THEN 120.00 ELSE 0
                END,
                CASE
                    WHEN c.channel = 'paid_search' AND d IN (CURRENT_DATE - 1, CURRENT_DATE - 25) THEN 0
                    WHEN c.channel = 'paid_search' THEN 3570.00
                    WHEN c.channel = 'email' AND d BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE - 5 THEN 2100.00
                    WHEN c.channel = 'email' THEN 1280.00
                    WHEN c.channel = 'organic' AND d = CURRENT_DATE - 1 THEN 5200.00
                    WHEN c.channel = 'organic' THEN 6650.00 ELSE 0
                END
            FROM (VALUES ('paid_search'), ('email'), ('organic')) AS c(channel),
                 generate_series(CURRENT_DATE - 29, CURRENT_DATE, '1 day'::interval) AS d
            ON CONFLICT (channel, date) DO NOTHING
        """))

        # ── Product views ─────────────────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO product_views (product_id, date, views) VALUES
                ('SKU-001', CURRENT_DATE - 1, 1800),
                ('SKU-002', CURRENT_DATE - 1, 1200),
                ('SKU-003', CURRENT_DATE - 1, 900),
                ('SKU-004', CURRENT_DATE - 1, 400),
                ('SKU-005', CURRENT_DATE - 1, 300)
            ON CONFLICT (product_id, date) DO NOTHING
        """))

        # ── Support tickets ───────────────────────────────────────────────────
        await conn.execute(text("""
            INSERT INTO support_tickets (created_at, category, sentiment, resolved) VALUES
                (NOW() - interval '1 day',          'Out of stock / can''t purchase', 'negative', false),
                (NOW() - interval '1 day 1 hour',   'Out of stock / can''t purchase', 'negative', false),
                (NOW() - interval '1 day 2 hours',  'Out of stock / can''t purchase', 'negative', false),
                (NOW() - interval '1 day 3 hours',  'Out of stock / can''t purchase', 'negative', false),
                (NOW() - interval '1 day 4 hours',  'Out of stock / can''t purchase', 'negative', true),
                (NOW() - interval '1 day 5 hours',  'Order delayed / shipping issue', 'negative', false),
                (NOW() - interval '1 day 6 hours',  'Order delayed / shipping issue', 'negative', false),
                (NOW() - interval '1 day 7 hours',  'Refund request',                 'negative', false),
                (NOW() - interval '1 day 8 hours',  'Refund request',                 'negative', true),
                (NOW() - interval '1 day 9 hours',  'General inquiry',                'neutral',  true),
                (NOW() - interval '2 days',         'Out of stock / can''t purchase', 'negative', true),
                (NOW() - interval '2 days 2 hours', 'Refund request',                 'negative', false),
                (NOW() - interval '2 days 4 hours', 'General inquiry',                'neutral',  true),
                (NOW() - interval '3 days',         'General inquiry',                'neutral',  true),
                (NOW() - interval '3 days 3 hours', 'Product question',               'neutral',  true),
                (NOW() - interval '4 days',         'General inquiry',                'neutral',  true),
                (NOW() - interval '4 days 5 hours', 'Delivery update',                'neutral',  true),
                (NOW() - interval '5 days',         'Promo code inquiry',             'neutral',  true),
                (NOW() - interval '5 days 1 hour',  'Promo code inquiry',             'neutral',  true),
                (NOW() - interval '5 days 2 hours', 'General inquiry',                'neutral',  true),
                (NOW() - interval '6 days',         'Promo code inquiry',             'positive', true),
                (NOW() - interval '6 days 2 hours', 'Product question',               'neutral',  true),
                (NOW() - interval '25 days',        'Out of stock / can''t purchase', 'negative', true),
                (NOW() - interval '25 days 1 hour', 'Out of stock / can''t purchase', 'negative', true),
                (NOW() - interval '25 days 2 hours','Refund request',                 'negative', true),
                (NOW() - interval '25 days 3 hours','General inquiry',                'neutral',  true)
        """))

    _log.info("Seed complete.")
