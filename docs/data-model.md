# Data Model

## PostgreSQL Entity-Relationship Diagram

```mermaid
erDiagram
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

    daily_sales {
        date date PK
        numeric revenue
        int order_count
        numeric avg_order_value
    }

    products {
        varchar32 id PK
        text name
        text category
        numeric price
    }

    inventory {
        varchar32 product_id FK
        date date
        int stock_level
        int reorder_point
        PRIMARY KEY product_id_date
    }

    campaigns {
        varchar32 id PK
        text name
        varchar32 channel
        varchar16 status
        numeric daily_budget
    }

    support_tickets {
        uuid id PK
        timestamptz created_at
        varchar64 category
        varchar16 sentiment
        boolean resolved
    }

    product_daily_sales {
        varchar32 product_id FK
        date date
        int units_sold
        numeric revenue
        PRIMARY KEY product_id_date
    }

    regional_sales {
        varchar64 region
        date date
        numeric revenue
        int order_count
        PRIMARY KEY region_date
    }

    campaign_daily_metrics {
        varchar32 campaign_id FK
        date date
        numeric spend
        int impressions
        int clicks
        int conversions
        numeric revenue
        PRIMARY KEY campaign_id_date
    }

    channel_daily_performance {
        varchar32 channel
        date date
        numeric spend
        numeric revenue
        PRIMARY KEY channel_date
    }

    promotions {
        varchar32 id PK
        text name
        numeric discount_pct
        text_array products
        varchar16 status
        timestamptz scheduled_at
    }

    product_views {
        varchar32 product_id FK
        date date
        int views
        PRIMARY KEY product_id_date
    }

    incidents ||--o{ incident_actions : "has"
    products ||--o{ inventory : "tracks"
    products ||--o{ product_daily_sales : "has"
    products ||--o{ product_views : "tracks"
    campaigns ||--o{ campaign_daily_metrics : "has"
```

---

## Domain Model Class Diagram

```mermaid
classDiagram
    class DailyRevenue {
        +date date
        +float revenue
        +int order_count
        +float avg_order_value
    }
    class ProductSales {
        +str product_id
        +str name
        +float revenue
        +int units_sold
    }
    class AnomalyResult {
        +date date
        +str metric
        +float expected
        +float actual
        +str severity
    }
    class StockLevel {
        +str product_id
        +str name
        +int stock_level
        +int threshold
    }
    class StockoutEvent {
        +str product_id
        +date date
        +int lost_views
    }
    class CampaignMetric {
        +str campaign_id
        +str name
        +str channel
        +float spend
        +float roas
        +str status
    }
    class TicketVolumeSummary {
        +str category
        +int count
        +float pct_change
    }
    class RefundRateSummary {
        +float rate
        +float baseline
        +float delta_pct
    }

    note for DailyRevenue "Sales domain"
    note for StockLevel "Inventory domain"
    note for CampaignMetric "Marketing domain"
    note for TicketVolumeSummary "Support domain"
```

---

## Action Model Class Diagram

```mermaid
classDiagram
    class ProposedAction {
        +str action_id
        +str action_type
        +dict parameters
        +str justification
        +str impact_estimate
        +bool reversible = True
    }
    class ApprovedAction {
        +str action_id
        +str action_type
        +dict parameters
        +str approved_at
    }
    class ActionResult {
        +str action_id
        +str action_type
        +bool success
        +str message
        +str executed_at
    }

    ProposedAction --> ApprovedAction : human approves
    ApprovedAction --> ActionResult : execute_actions node
```

### Supported `action_type` values

| `action_type` | Required parameters |
|---|---|
| `restock_product` | `product_id`, `quantity` |
| `apply_discount` | `product_id`, `discount_pct` |
| `pause_campaign` | `campaign_id` |
| `resume_campaign` | `campaign_id` |
| `create_support_ticket` | `category`, `description` |

---

## API Request/Response Models

```mermaid
classDiagram
    class ChatRequest {
        +str content
        +str session_id
    }
    class ApprovalRequest {
        +str request_id
        +list~str~ approved_action_ids
    }
    class DeclineRequest {
        +str request_id
    }
    class IncidentSummary {
        +str id
        +str created_at
        +str query
        +str root_cause
        +list~str~ domains
        +float confidence
        +bool resolved
    }
```

---

## Qdrant Collection Schema

```mermaid
classDiagram
    class QdrantPoint {
        +str id
        +list~float~ vector
        +QdrantPayload payload
    }
    class QdrantPayload {
        +str incident_id
        +str date
        +str query
        +str root_cause
        +list~str~ domains
        +float confidence
        +list~str~ actions_taken
    }

    QdrantPoint --> QdrantPayload

    note for QdrantPoint "collection: incidents\n1536-dim cosine\nthreshold: 0.72\ntop-k: 3"
```

---

## Redis Key Structure

```mermaid
flowchart LR
    K["session:{session_id}:context"] --> V["JSON:\nlast_incident_id\ncontext_summary\nproposed_actions\nlast_query"]
    note["No explicit TTL\ndata persists until Redis restart"] -.-> K
```
