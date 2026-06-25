# Database — Ecomm Ops Brain

## PostgreSQL — Entity Relationship Diagram

```mermaid
erDiagram
    products {
        varchar32 id PK
        text name
        text category
        numeric price
    }

    inventory {
        varchar32 product_id PK,FK
        date date PK
        int stock_level
        int reorder_point
    }

    product_daily_sales {
        varchar32 product_id PK,FK
        date date PK
        int units_sold
        numeric revenue
    }

    product_views {
        varchar32 product_id PK,FK
        date date PK
        int views
    }

    daily_sales {
        date date PK
        numeric revenue
        int order_count
        numeric avg_order_value
    }

    regional_sales {
        varchar64 region PK
        date date PK
        numeric revenue
        int order_count
    }

    campaigns {
        varchar32 id PK
        text name
        varchar32 channel
        varchar16 status
        numeric daily_budget
    }

    campaign_daily_metrics {
        varchar32 campaign_id PK,FK
        date date PK
        numeric spend
        int impressions
        int clicks
        int conversions
        numeric revenue
    }

    channel_daily_performance {
        varchar32 channel PK
        date date PK
        numeric spend
        numeric revenue
    }

    promotions {
        varchar64 id PK
        text name
        numeric discount_pct
        text_array products
        varchar16 status
        timestamptz scheduled_at
    }

    support_tickets {
        varchar36 id PK
        timestamptz created_at
        varchar64 category
        varchar16 sentiment
        boolean resolved
    }

    incidents {
        varchar36 id PK
        timestamptz created_at
        text query
        text root_cause
        text_array domains
        float confidence
        varchar128 embedding_id
        boolean resolved
    }

    incident_actions {
        uuid id PK
        varchar36 incident_id FK
        varchar64 action_type
        text parameters
        boolean approved
        timestamptz executed_at
        text outcome
    }

    products ||--o{ inventory : "stock tracked by"
    products ||--o{ product_daily_sales : "sales tracked by"
    products ||--o{ product_views : "views tracked by"
    campaigns ||--o{ campaign_daily_metrics : "metrics tracked by"
    incidents ||--o{ incident_actions : "actions taken"
```

---

## Table Descriptions

### Operational — Sales

**`daily_sales`** — Aggregate revenue metrics per day. Source of truth for `get_daily_revenue()` and anomaly detection (z-score over 30-day window).

**`product_daily_sales`** — Per-product revenue and unit sales by day. Powers `get_product_sales_breakdown()`.

**`product_views`** — Daily page view counts per product. Powers `get_views_vs_purchases()` — views joined with `product_daily_sales` to compute conversion rate.

**`regional_sales`** — Revenue and order count by region per day. Powers `get_regional_sales()` and regional anomaly detection.

### Operational — Inventory

**`inventory`** — Stock level and reorder point per product per day. `days_of_stock` is computed at query time as `stock_level / avg_daily_sales`. Status is derived: `out_of_stock` if 0, `low` if below `reorder_point`, else `ok`.

### Operational — Marketing

**`campaigns`** — Campaign master data. `status` is `active` or `paused`; action tools update this directly.

**`campaign_daily_metrics`** — Daily spend, impressions, clicks, conversions, and revenue per campaign. ROAS computed at query time as `revenue / spend`.

**`channel_daily_performance`** — Aggregated spend and revenue by channel (paid_search, email, organic, social) per day. ROAS and conversion rates computed at query time.

**`promotions`** — Discount promotions. Action tool `apply_discount` inserts rows here. `products` is a `TEXT[]` array of product IDs the promo applies to.

### Operational — Support

**`support_tickets`** — Individual support tickets. `category` (e.g. `stockout`, `shipping`, `refund`) and `sentiment` (`positive`, `neutral`, `negative`) are used to compute complaint theme counts and refund rate summaries. Complaint themes derived by GROUP BY on `category`.

### System

**`incidents`** — One row per completed DIAGNOSTIC/ACTION/HYBRID/MEMORY query turn. Written by `_persist_incident_to_postgres()` after every successful `store_incident`. Qdrant is the source of truth for semantic retrieval; Postgres provides queryable history via `GET /incidents`.

**`incident_actions`** — One row per executed action, linked to its parent incident. `parameters` stored as JSON string. Written by action tools after execution.

**`checkpoint_*`** — LangGraph `AsyncPostgresSaver` tables (`checkpoint_blobs`, `checkpoint_migrations`, `checkpoint_writes`). Managed entirely by `langgraph-checkpoint-postgres`. Full `OpsState` is serialized here after every graph node. HITL `interrupt()` state is persisted here and restored on `Command(resume=...)`.

---

## Qdrant — incidents Collection

```mermaid
classDiagram
    class PointStruct {
        +str id
        +list~float~ vector
        +Payload payload
    }

    class Payload {
        +str incident_id
        +str date
        +str query
        +str root_cause
        +list~str~ domains
        +float confidence
        +list~str~ actions_taken
    }

    PointStruct --> Payload
```

| Property | Value |
|---|---|
| Collection name | `incidents` (configurable via `QDRANT_COLLECTION`) |
| Vector size | 1536 dimensions |
| Distance metric | Cosine |
| Embedding model | Azure OpenAI `text-embedding-3-small-1` |
| Retrieval threshold | `score_threshold = 0.5` |
| Retrieval limit | `top_k = 3` |

**Vector text construction:**
```
{user_query} | root_cause: {root_cause[:400]} | sales_findings: {json[:200]} | inventory_findings: {json[:200]} | ...
```

All four domain findings are included if present. A richer, domain-specific query string will embed closer to stored incident vectors than a short generic one.

---

## Action Model

```mermaid
classDiagram
    class ProposedAction {
        +str action_id
        +str action_type
        +dict parameters
        +str justification
        +str impact_estimate
        +bool reversible
    }
    class ActionResult {
        +str action_id
        +str action_type
        +bool success
        +str message
        +str executed_at
    }

    ProposedAction --> ActionResult : HITL approve → execute
```

| `action_type` | Required parameters | DB operation |
|---|---|---|
| `restock_product` | `product_id`, `quantity` | INSERT/UPDATE inventory stock_level |
| `apply_discount` | `product_id`, `discount_pct` | INSERT INTO promotions |
| `pause_campaign` | `campaign_id` | UPDATE campaigns SET status='paused' |
| `resume_campaign` | `campaign_id` | UPDATE campaigns SET status='active' |
| `create_support_ticket` | `issue_type`, `description` | INSERT INTO support_tickets |

---

## Schema Management

### ORM Models

Tables are defined as SQLAlchemy 2.0 ORM models in `backend/app/db/models/`:

| File | Models |
|---|---|
| `ops_data.py` | `Product`, `Inventory`, `DailySales`, `ProductDailySales`, `RegionalSales`, `Campaign`, `CampaignDailyMetrics`, `ChannelDailyPerformance`, `Promotion`, `ProductViews`, `SupportTicket` |
| `incidents.py` | `Incident`, `IncidentAction` |

All models inherit from a shared `Base(DeclarativeBase)` in `base.py`. Schema creation runs at startup:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

`create_all` is idempotent — it only creates tables that don't exist yet. Existing tables and their data are never touched.

### Seed Data

`backend/app/db/seed.py` seeds all 11 operational tables on startup with 30 days of realistic mock data (weekly patterns, yesterday set as a "bad day" — SKU-001/002/003 stocked out, CAMP-001 paused).

The seeder is idempotent: it checks `SELECT COUNT(*) FROM products` first and skips entirely if data already exists. This means the named Docker volume (`pgdata`) preserves data across container rebuilds — the seed only runs on a fresh database.
