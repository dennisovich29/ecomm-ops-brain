-- Seed data — idempotent (ON CONFLICT DO NOTHING)
-- Mirrors the mock repository scenario: yesterday is always a "bad day"

INSERT INTO products (id, name, category, price) VALUES
    ('SKU-001', 'Wireless Headphones Pro', 'Electronics', 89.99),
    ('SKU-002', 'Running Shoes X2',        'Footwear',    74.99),
    ('SKU-003', 'Yoga Mat Premium',        'Fitness',     49.99),
    ('SKU-004', 'Coffee Grinder 500',      'Kitchen',     39.99),
    ('SKU-005', 'Laptop Stand Foldable',   'Electronics', 34.99)
ON CONFLICT (id) DO NOTHING;

INSERT INTO campaigns (id, name, channel, status, daily_budget) VALUES
    ('CAMP-001', 'Google Shopping — Electronics', 'paid_search', 'paused', 850.00),
    ('CAMP-002', 'Email — Weekly Deals',           'email',       'active', 120.00)
ON CONFLICT (id) DO NOTHING;

INSERT INTO daily_sales (date, revenue, order_count, avg_order_value)
SELECT
    (CURRENT_DATE - (s.i || ' days')::interval)::date,
    CASE WHEN s.i = 1 THEN 31525.00 ELSE 48500.00 END,
    CASE WHEN s.i = 1 THEN 230       ELSE 320       END,
    CASE WHEN s.i = 1 THEN 137.07    ELSE 151.56    END
FROM generate_series(0, 29) AS s(i)
ON CONFLICT (date) DO NOTHING;

INSERT INTO inventory (product_id, date, stock_level) VALUES
    ('SKU-001', CURRENT_DATE, 0),
    ('SKU-002', CURRENT_DATE, 0),
    ('SKU-003', CURRENT_DATE, 0),
    ('SKU-004', CURRENT_DATE, 12),
    ('SKU-005', CURRENT_DATE, 250)
ON CONFLICT (product_id, date) DO NOTHING;

INSERT INTO support_tickets (id, created_at, category, sentiment, resolved) VALUES
    ('a1b2c3d4-0001-0001-0001-000000000001', NOW() - interval '1 day', 'Out of stock / can''t purchase', 'negative', false),
    ('a1b2c3d4-0001-0001-0001-000000000002', NOW() - interval '1 day', 'Out of stock / can''t purchase', 'negative', false),
    ('a1b2c3d4-0001-0001-0001-000000000003', NOW() - interval '1 day', 'Out of stock / can''t purchase', 'negative', false),
    ('a1b2c3d4-0001-0001-0001-000000000004', NOW() - interval '1 day', 'Out of stock / can''t purchase', 'negative', false),
    ('a1b2c3d4-0001-0001-0001-000000000005', NOW() - interval '1 day', 'Order delayed / shipping issue', 'negative', false),
    ('a1b2c3d4-0001-0001-0001-000000000006', NOW() - interval '1 day', 'Order delayed / shipping issue', 'negative', false),
    ('a1b2c3d4-0001-0001-0001-000000000007', NOW() - interval '1 day', 'Refund request',                 'negative', false),
    ('a1b2c3d4-0001-0001-0001-000000000008', NOW() - interval '1 day', 'Refund request',                 'negative', true),
    ('a1b2c3d4-0001-0001-0001-000000000009', NOW(),                    'General inquiry',                'neutral',  true),
    ('a1b2c3d4-0001-0001-0001-000000000010', NOW(),                    'General inquiry',                'neutral',  false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO incidents (id, created_at, query, root_cause, domains, confidence, resolved) VALUES
    (
        'INC-2024-001',
        NOW() - interval '1 day 2 hours',
        'Why did revenue drop 35% yesterday?',
        'Simultaneous stockouts on top 3 SKUs (SKU-001, SKU-002, SKU-003) eliminated $15,000+ in potential revenue. Google Shopping campaign CAMP-001 was paused on the same day, compounding the organic traffic loss.',
        ARRAY['sales', 'inventory', 'marketing'],
        0.92,
        false
    ),
    (
        'INC-2024-002',
        NOW() - interval '3 days',
        'Support ticket volume spike — 130% above 7-day average',
        'Delayed restock on SKU-003 (Yoga Mat Premium) caused a 48-hour stockout, generating 22 out-of-stock complaints and a secondary wave of refund requests.',
        ARRAY['support', 'inventory'],
        0.85,
        true
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO incident_actions (id, incident_id, action_type, parameters, approved, executed_at, outcome) VALUES
    (
        'b2c3d4e5-0001-0001-0001-000000000001',
        'INC-2024-001',
        'restock_order',
        '{"product_id": "SKU-001", "quantity": 500, "supplier": "primary", "priority": "urgent"}',
        true,
        NOW() - interval '23 hours',
        'Restock order placed. Estimated arrival 48-72 hours.'
    ),
    (
        'b2c3d4e5-0001-0001-0001-000000000002',
        'INC-2024-001',
        'restock_order',
        '{"product_id": "SKU-002", "quantity": 300, "supplier": "primary", "priority": "urgent"}',
        true,
        NOW() - interval '23 hours',
        'Restock order placed. Estimated arrival 48-72 hours.'
    ),
    (
        'b2c3d4e5-0001-0001-0001-000000000003',
        'INC-2024-001',
        'restock_order',
        '{"product_id": "SKU-003", "quantity": 200, "supplier": "primary", "priority": "urgent"}',
        true,
        NOW() - interval '22 hours',
        'Restock order placed. Estimated arrival 48-72 hours.'
    ),
    (
        'b2c3d4e5-0001-0001-0001-000000000004',
        'INC-2024-001',
        'resume_campaign',
        '{"campaign_id": "CAMP-001", "budget_adjustment": 0}',
        false,
        null,
        null
    ),
    (
        'b2c3d4e5-0001-0001-0002-000000000001',
        'INC-2024-002',
        'restock_order',
        '{"product_id": "SKU-003", "quantity": 200, "supplier": "secondary", "priority": "standard"}',
        true,
        NOW() - interval '3 days',
        'Restock completed. Stock level restored to 200 units.'
    )
ON CONFLICT (id) DO NOTHING;
