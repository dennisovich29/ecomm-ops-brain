# Agent Design

## LangGraph Workflow

```mermaid
flowchart TD
    START([START]) --> RI[route_intent\nclassify query · extract domains\ntime range · entities]

    RI -- "GENERAL or no domains" --> FR[format_response]

    RI --> DISPATCH{edge_dispatch_agents\nwhich domains?}

    DISPATCH --> SA[run_sales_agent\nReAct · 6 tools]
    DISPATCH --> IA[run_inventory_agent\nReAct · 5 tools]
    DISPATCH --> MA[run_marketing_agent\nReAct · 5 tools]
    DISPATCH --> SUA[run_support_agent\nReAct · 4 tools]

    SA --> RF[run_reflection\nconfidence scoring\ngap detection]
    IA --> RF
    MA --> RF
    SUA --> RF

    RF -- "SUMMARY" --> FR
    RF --> RC{edge_after_reflection\nconfidence ≥ 0.70\nor passes ≥ 3?}

    RC -- re_query --> RI
    RC -- synthesize --> MEM[retrieve_memory\nQdrant similarity search]

    MEM --> SY[synthesize_findings\nLLM root cause analysis\nincludes prior_context]

    SY --> SYE{edge_after_synthesis\nquery_type?}

    SYE -- "DIAGNOSTIC / MEMORY / SUMMARY" --> FR
    SYE -- "ACTION / HYBRID" --> PA[propose_actions\nLLM proposes parameterized actions]

    PA --> HC[hitl_checkpoint\ninterrupt — graph suspends]

    HC -- human resumes --> HCE{edge_after_hitl\nactions approved?}
    HCE -- yes --> EA[execute_actions\nwrites to Postgres DB]
    HCE -- no --> FR

    EA --> SI[store_incident\nQdrant + Postgres]
    SI --> FR

    FR --> END([END])

    style HC fill:#f90,color:#000
    style RF fill:#6af,color:#000
    style PA fill:#9f6,color:#000
```

---

## OpsState Schema

```mermaid
classDiagram
    class OpsState {
        +str user_query
        +str session_id
        +str turn_id
        +Intent intent
        +list~str~ active_agents
        +dict sales_findings
        +dict inventory_findings
        +dict marketing_findings
        +dict support_findings
        +list~str~ reflection_notes
        +float confidence_score
        +list~str~ gaps_identified
        +int reflection_passes
        +list~dict~ similar_incidents
        +str current_incident_id
        +list~dict~ proposed_actions
        +list~dict~ approved_actions
        +list~dict~ executed_actions
        +str root_cause_analysis
        +list~str~ recommendations
        +dict final_response
        +str prior_context
        +list messages
    }

    class Intent {
        +str query_type
        +list~str~ domains
        +TimeRange time_range
        +list~str~ entities
    }

    class TimeRange {
        +str start
        +str end
    }

    OpsState --> Intent
    Intent --> TimeRange
```

---

## Agent Tools

```mermaid
classDiagram
    class SalesAgent {
        get_daily_revenue()
        get_order_volume()
        get_product_sales_breakdown()
        get_regional_sales()
        detect_sales_anomaly()
        compare_periods()
    }

    class InventoryAgent {
        get_stock_levels()
        get_low_stock_alerts()
        get_stockout_events()
        get_views_vs_purchases()
        get_restock_recommendations()
    }

    class MarketingAgent {
        get_campaign_metrics()
        get_channel_performance()
        get_active_promotions()
        get_promotion_schedule()
        get_roas_by_channel()
    }

    class SupportAgent {
        get_ticket_volume()
        get_refund_rates()
        get_return_rates()
        get_common_complaint_themes()
    }

    class ISalesRepository
    class IInventoryRepository
    class IMarketingRepository
    class ISupportRepository

    SalesAgent --> ISalesRepository
    InventoryAgent --> IInventoryRepository
    MarketingAgent --> IMarketingRepository
    SupportAgent --> ISupportRepository
```

---

## Reflection Agent Logic

```mermaid
flowchart TD
    A([enter reflect]) --> B[count populated domain findings]
    B --> C[base_score = populated / required_domains]
    C --> D{corroboration checks}
    D --> D1[+0.1 if stockouts AND revenue present]
    D --> D2[+0.1 if campaign issues AND revenue present]
    D --> D3[+0.1 if complaint themes AND stockouts present]
    D1 & D2 & D3 --> E[confidence = min base + bonus, 1.0]
    E --> F{gaps_identified\nAND passes < 3\nAND confidence < 0.70?}
    F -- yes --> G[return re_query]
    F -- no --> H[return synthesize]
```

---

## Repository Pattern

```mermaid
classDiagram
    direction LR
    class ISalesRepository {
        <<interface>>
        +get_daily_revenue()
        +get_order_volume()
        +get_product_sales_breakdown()
        +get_regional_sales()
        +detect_sales_anomaly()
        +compare_periods()
    }

    class MockSalesRepository {
        in-memory seed data
    }

    class PostgresSalesRepository {
        SQLAlchemy async queries
    }

    ISalesRepository <|.. MockSalesRepository
    ISalesRepository <|.. PostgresSalesRepository

    class RepositoryFactory {
        +get_sales_repo() ISalesRepository
        +get_inventory_repo() IInventoryRepository
        +get_marketing_repo() IMarketingRepository
        +get_support_repo() ISupportRepository
    }

    note for RepositoryFactory "REPO_BACKEND env var\nv1 (or mock) → Mock\nv2 (or postgres) → Postgres"

    RepositoryFactory --> ISalesRepository
```

---

## Memory Architecture

```mermaid
flowchart LR
    subgraph Working["Working Memory (Redis)"]
        WM["session:{id}:context\nlast_incident_id\ncontext_summary\nproposed_actions\nlast_query"]
    end

    subgraph Episodic["Episodic Memory (Qdrant)"]
        QV["incident vectors\n1536-dim cosine\nthreshold 0.72\ntop-k 3"]
    end

    subgraph Structured["Structured Memory (Postgres)"]
        PT[incidents table\nincident_actions table]
    end

    CHAT([chat turn]) --> WM
    WM --> CHAT

    RESOLVE([incident resolved]) --> QV
    RESOLVE --> PT
    QV --> RETRIEVE([retrieve_memory node])
    PT --> INCIDENTS([GET /incidents])
```


All nodes read from and write to a single `OpsState` TypedDict. The LangGraph checkpointer persists this per thread.

```python
class OpsState(TypedDict):
    # Input
    user_query: str
    session_id: str
    turn_id: str

    # Routing
    intent: Optional[Intent]       # query_type, domains, time_range, entities
    active_agents: list[str]       # domain names dispatched this turn

    # Agent findings
    sales_findings: Optional[dict]
    inventory_findings: Optional[dict]
    marketing_findings: Optional[dict]
    support_findings: Optional[dict]

    # Reflection
    reflection_notes: list[str]
    confidence_score: float        # 0.0 – 1.0
    gaps_identified: list[str]     # e.g. ["missing_inventory_data"]
    reflection_passes: int

    # Memory
    similar_incidents: list[dict]
    current_incident_id: Optional[str]

    # Actions
    proposed_actions: list[dict]   # ProposedAction dicts
    approved_actions: list[dict]
    executed_actions: list[dict]

    # Response
    root_cause_analysis: Optional[str]
    recommendations: list[str]
    final_response: Optional[dict]

    # Conversation
    messages: Annotated[list, add_messages]
```

### Intent schema

```python
class Intent(TypedDict):
    query_type: str       # DIAGNOSTIC | ACTION | MEMORY | SUMMARY | HYBRID | GENERAL
    domains: list[str]    # subset of [sales, inventory, marketing, support]
    time_range: TimeRange # { start: "YYYY-MM-DD", end: "YYYY-MM-DD" }
    entities: list[str]   # product names, campaign IDs, SKUs
```

