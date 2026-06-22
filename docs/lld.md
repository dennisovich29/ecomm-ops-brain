# Low-Level Design — Ecomm Ops Brain

## 1. Directory Structure

```
ecomm-ops-brain/
├── backend/
│   └── app/
│       ├── agents/
│       │   ├── intent_router.py      # LLM structured-output classifier
│       │   ├── sales_agent.py        # create_agent factory (LangChain v1)
│       │   ├── inventory_agent.py
│       │   ├── marketing_agent.py
│       │   ├── support_agent.py
│       │   ├── reflection_agent.py   # Pure-Python confidence scorer
│       │   ├── action_agent.py       # LLM action proposal
│       │   └── middleware.py         # SummarizationMiddleware, PIIMiddleware, wrap_tool_call
│       ├── api/routes/
│       │   ├── chat.py               # POST /chat/stream (SSE)
│       │   ├── actions.py            # POST /actions/approve|decline
│       │   ├── incidents.py          # GET /incidents
│       │   └── health.py             # GET /health  GET /ready
│       ├── core/
│       │   ├── config.py             # Pydantic Settings (env vars)
│       │   ├── llm.py                # AzureChatOpenAI + AzureOpenAIEmbeddings factories
│       │   ├── observability.py      # Langfuse callback factory
│       │   └── exceptions.py        # Custom exceptions + FastAPI handlers
│       ├── db/
│       │   ├── postgres.py           # Async engine, session factory
│       │   ├── qdrant.py             # AsyncQdrantClient factory, ensure_collection
│       │   ├── checkpointer.py       # AsyncPostgresSaver setup
│       │   └── migrations/           # SQL migration files
│       ├── graph/
│       │   ├── state.py              # OpsState TypedDict, Intent, TimeRange
│       │   ├── nodes.py              # All 13 graph node functions
│       │   ├── edges.py              # Conditional edge functions
│       │   └── workflow.py           # build_graph(), init_compiled_graph()
│       ├── memory/
│       │   ├── episodic.py           # store_incident(), retrieve_similar_incidents()
│       │   └── structured.py         # Postgres incident queries
│       ├── models/
│       │   ├── domain.py             # DailyRevenue, StockLevel, CampaignMetric, etc.
│       │   ├── actions.py            # ProposedAction Pydantic model
│       │   └── api.py                # ChatRequest, ApprovalRequest, DeclineRequest
│       ├── repositories/
│       │   ├── interfaces.py         # Protocol interfaces for all 4 domains
│       │   ├── factory.py            # get_*_repo() factory functions
│       │   └── postgres/             # PostgresImpl for each domain
│       └── tools/
│           ├── sales_tools.py        # LangChain tools wrapping ISalesRepository
│           ├── inventory_tools.py
│           ├── marketing_tools.py
│           ├── support_tools.py
│           └── action_tools.py       # execute_action() dispatcher
└── frontend/
    └── src/
        ├── app/
        │   └── api/                  # Next.js proxy routes
        ├── components/               # Sidebar, ChatArea, MessageBubble, ApprovalCard
        ├── hooks/
        │   └── useChat.js            # SSE stream handler
        └── lib/
            ├── api.js                # fetch helpers
            └── store.js              # Zustand store
```

---

## 2. LangGraph Workflow

### 2.1 Full Node Graph

```mermaid
graph TD
    START --> route_intent

    route_intent -->|"GENERAL or no domains"| format_response

    route_intent -->|"has domains"| DISPATCH
    subgraph DISPATCH["Parallel Dispatch"]
        run_sales_agent
        run_inventory_agent
        run_marketing_agent
        run_support_agent
    end

    run_sales_agent --> run_reflection
    run_inventory_agent --> run_reflection
    run_marketing_agent --> run_reflection
    run_support_agent --> run_reflection

    run_reflection -->|"SUMMARY"| format_response
    run_reflection -->|"confidence < 0.70 AND gaps AND passes < 3"| route_intent
    run_reflection -->|"else"| retrieve_memory

    retrieve_memory --> synthesize_findings
    synthesize_findings --> store_incident

    store_incident -->|"ACTION or HYBRID + action_requested=true"| propose_actions
    store_incident -->|"else"| format_response

    propose_actions --> hitl_checkpoint
    hitl_checkpoint -->|"approved_actions non-empty"| execute_actions
    hitl_checkpoint -->|"no approved actions"| format_response

    execute_actions --> format_response
    format_response --> END
```

### 2.2 OpsState

```python
class Intent(TypedDict):
    query_type: str           # DIAGNOSTIC | ACTION | MEMORY | SUMMARY | HYBRID | GENERAL
    domains: list[str]        # subset of [sales, inventory, marketing, support]
    time_range: TimeRange     # {start: ISO, end: ISO}
    entities: list[str]       # product names, campaign IDs, SKU IDs
    action_requested: bool    # True only when user explicitly asked for an action

class OpsState(TypedDict):
    # Input
    user_query: str
    session_id: str
    turn_id: str

    # Routing
    intent: Intent
    active_agents: list[str]

    # Agent findings
    sales_findings: dict | None
    inventory_findings: dict | None
    marketing_findings: dict | None
    support_findings: dict | None

    # Reflection
    reflection_notes: list[str]
    confidence_score: float
    gaps_identified: list[str]
    reflection_passes: int

    # Memory
    similar_incidents: list[dict]
    current_incident_id: str | None

    # Actions
    proposed_actions: list[dict]
    approved_actions: list[dict]
    executed_actions: list[dict]

    # Response
    root_cause_analysis: str | None
    recommendations: list[str]
    final_response: dict | None
    prior_context: str | None
    messages: Annotated[list, add_messages]
```

### 2.3 Conditional Edge Logic

| Edge function | Source node | Decision |
|---|---|---|
| `edge_dispatch_agents` | `route_intent` | Returns list of agent node names for parallel dispatch; `["format_response"]` for GENERAL or empty domains |
| `edge_after_reflection` | `run_reflection` | `"format_response"` for SUMMARY; else calls `should_re_query()` → `"re_query"` or `"synthesize"` |
| `edge_after_synthesis` | `store_incident` | `"propose_actions"` if `query_type == ACTION` or `(HYBRID and action_requested)`; else `"format_response"` |
| `edge_after_hitl` | `hitl_checkpoint` | `"execute_actions"` if `approved_actions` non-empty; else `"format_response"` |

### 2.4 Checkpointing

`thread_id = session_id` — LangGraph reuses the same thread for every turn within a session. `AsyncPostgresSaver` (from `langgraph-checkpoint-postgres`) persists full `OpsState` to PostgreSQL `checkpoint_*` tables after every node. Conversation history accumulates in `OpsState.messages` via the `add_messages` reducer.

The `synthesize_findings` node reads `messages[-6:]` (last 3 turns) as follow-up context, injected into the synthesis prompt.

---

## 3. Agent Designs

### 3.1 Intent Router

- **Type:** Single-shot LLM call with structured output
- **Chain:** `ChatPromptTemplate | llm.with_structured_output(IntentOutput)`
- **Output model:** `IntentOutput` (Pydantic) — `query_type`, `domains`, `time_range`, `entities`, `action_requested`
- **Fallback:** if `time_range.start` is empty → defaults to yesterday

### 3.2 Specialist Agents

All four use `create_agent` from `langchain.agents` (LangChain v1 — `create_react_agent` from `langgraph.prebuilt` is deprecated). They think → call a tool → observe → repeat until confident enough to emit a final JSON answer. Middleware is passed as a `middleware=[]` parameter.

| Agent | Tools |
|---|---|
| Sales | `get_daily_revenue`, `detect_sales_anomaly`, `compare_sales_periods`, `get_product_sales_breakdown`, `get_regional_sales` |
| Inventory | `get_stock_levels`, `get_stockout_events`, `get_restock_recommendations`, `get_views_vs_purchases` |
| Marketing | `get_campaign_metrics`, `get_channel_performance`, `get_active_promotions` |
| Support | `get_ticket_volume`, `get_refund_rates`, `get_complaint_themes` |

Middleware applied per agent (passed as `middleware=[]` to `create_agent`):
- All agents: `SummarizationMiddleware(model=llm, trigger=("tokens", 2000), keep=("messages", 20))`, `resilient_tool_call` (via `@wrap_tool_call`)
- Support agent additionally: `PIIMiddleware("email", strategy="redact", apply_to_input=True)`, `PIIMiddleware("phone_number", detector=regex, strategy="redact", apply_to_input=True)`

### 3.3 Reflection Agent

Pure Python — no LLM call. Runs after all dispatched agents converge.

**Confidence scoring:**
- Base = `populated_domains / total_domains`
- +0.10 boost for each corroborating signal pair: stockout↔sales, campaign_issues↔sales, ticket↔stockout (capped +0.30)

**Decision (`should_re_query`):**
- `"re_query"` → gaps exist AND confidence < 0.70 AND passes < 3
- `"synthesize"` → otherwise (routes to `retrieve_memory`)

Max re-query passes: `MAX_REFLECTION_PASSES = 3`

### 3.4 Action Agent

Single-shot LLM call. Fetches real `products.id` and `campaigns.id` from DB before prompting to ground the output.

Supported `action_type` values: `restock_product`, `apply_discount`, `pause_campaign`, `resume_campaign`, `create_support_ticket`

Output is a JSON array validated against `ProposedAction` Pydantic model.

---

## 4. Repository Layer

All domain data access goes through Protocol interfaces. The factory functions return the only supported implementation:

```python
# repositories/factory.py
def get_sales_repo()     -> ISalesRepository:     return PostgresSalesRepository()
def get_inventory_repo() -> IInventoryRepository: return PostgresInventoryRepository()
def get_marketing_repo() -> IMarketingRepository: return PostgresMarketingRepository()
def get_support_repo()   -> ISupportRepository:   return PostgresSupportRepository()
```

Mock repositories (v1) have been removed. PostgreSQL is the only backend.

### Repository methods by domain

**Sales**

| Method | Returns |
|---|---|
| `get_daily_revenue(date)` | `DailyRevenue` — revenue, order count, DoD/WoW % |
| `get_product_breakdown(date)` | `list[ProductSales]` — per-product units + revenue share |
| `get_regional_breakdown(date)` | `list[RegionalSales]` — per-region revenue vs baseline |
| `detect_anomaly(date, window=30)` | `AnomalyResult` — z-score, severity, description |
| `compare_periods(date)` | `dict` — day/week/month revenue comparisons |

**Inventory**

| Method | Returns |
|---|---|
| `get_stock_levels(product_ids?)` | `list[StockLevel]` — stock, reorder point, days of stock, status |
| `get_stockout_events(date)` | `list[StockoutEvent]` — product, start/end, estimated lost revenue |
| `get_restock_recommendations()` | `list[RestockRecommendation]` — qty, urgency, reason |
| `get_views_vs_purchases(date)` | `list[dict]` — views/purchases/conversion per product |

**Marketing**

| Method | Returns |
|---|---|
| `get_campaign_metrics(date)` | `list[CampaignMetric]` — spend, impressions, clicks, CTR, ROAS |
| `get_channel_performance(date)` | `list[ChannelPerformance]` — per-channel revenue + conversion |
| `get_active_promotions()` | `list[ActivePromotion]` — discount %, products, status |

**Support**

| Method | Returns |
|---|---|
| `get_ticket_volume(date)` | `TicketVolumeSummary` — total, open, resolved, avg resolution time |
| `get_refund_rates(date)` | `RefundRateSummary` — refund count, % of orders, top reasons |
| `get_complaint_themes(date)` | `list[ComplaintTheme]` — theme label, count, sample messages |

---

## 5. Action Execution

`tools/action_tools.py` — `execute_action(action: dict)` dispatches to a handler by `action_type`.

| `action_type` | DB operation |
|---|---|
| `restock_product` | `INSERT INTO inventory ... ON CONFLICT DO UPDATE SET stock_level = stock_level + qty` |
| `apply_discount` | `INSERT INTO promotions (id, name, discount_pct, products, status, scheduled_at)` |
| `pause_campaign` | `UPDATE campaigns SET status = 'paused' WHERE id = ?` |
| `resume_campaign` | `UPDATE campaigns SET status = 'active' WHERE id = ?` |
| `create_support_ticket` | `INSERT INTO support_tickets (id, created_at, category, sentiment, resolved)` |

All handlers return `{"action_id": ..., "action_type": ..., "success": bool, "message": str, "executed_at": str}`.

---

## 6. Memory — Episodic

**Store (`store_incident`):**
1. Build text representation: `user_query | root_cause[:400] | sales_findings[:200] | ...`
2. Embed via `AzureOpenAIEmbeddings` (`text-embedding-3-small-1`, 1536-dim)
3. Upsert `PointStruct(id=incident_id, vector=..., payload={...})` to Qdrant `incidents` collection
4. Mirror to Postgres `incidents` table (non-blocking; Qdrant is source of truth)

**Retrieve (`retrieve_similar_incidents`):**
1. Build same text representation from current state
2. Embed with same model
3. `client.search(collection, query_vector, limit=3, score_threshold=0.5, with_payload=True)`
4. Returns list of incident dicts with `similarity_score` field

For memory queries to hit, the query text must share domain vocabulary with stored incident text — generic phrasing ("were there past issues") will likely fall below the 0.5 threshold.

---

## 7. API Endpoints

| Method | Path | Handler |
|---|---|---|
| `GET` | `/health` | Returns `{"status":"ok"}` — used by Docker healthcheck |
| `GET` | `/ready` | Probes Postgres + Qdrant; returns `{"status":"ready"\|"degraded","checks":{...}}` |
| `POST` | `/chat` | Synchronous graph run; returns JSON |
| `POST` | `/chat/stream` | SSE streaming — emits `token`, `final_response`, `error` events |
| `POST` | `/actions/approve` | Resumes HITL graph with `Command(resume={"approved_action_ids": [...]})` |
| `POST` | `/actions/decline` | Resumes HITL graph with `Command(resume={"approved_action_ids": []})` |
| `GET` | `/incidents` | Lists recent incidents from Postgres |

**SSE event schema:**
```
data: {"type": "token",          "content": "...partial text..."}
data: {"type": "final_response", "response": { <structured response dict> }}
data: {"type": "final_response", "response": {"type": "approval_pending", "proposed_actions": [...], "workflow_id": "<session_id>"}}
data: {"type": "error",          "message": "..."}
```

Token events are emitted only during the `synthesize_findings` node, filtered by `meta["langgraph_node"] == "synthesize_findings"`.

### Next.js Proxy Routes

| Proxy | Backend |
|---|---|
| `POST /api/chat/stream` | `POST /chat/stream` |
| `POST /api/actions/approve` | `POST /actions/approve` |
| `POST /api/actions/decline` | `POST /actions/decline` |
| `GET /api/incidents` | `GET /incidents` |

---

## 8. Frontend State (Zustand)

```js
{
  sessions: [],               // sidebar history
  activeSessionId: null,
  messagesBySession: {},      // { [sessionId]: Message[] }
  loadingBySession: {},       // { [sessionId]: boolean }
  sidebarOpen: true,
  incidents: [],
}
```

All message/loading state is keyed by `sessionId`. `useChat.js` captures `sessionId` at `sendMessage` call-time so in-flight SSE streams always write to the originating session if the user switches sessions mid-stream.

Selector fallbacks (`|| []`, `|| false`) are applied after `useStore()` returns — not inside the selector. Inline fallbacks inside selectors produce a new array reference on every render, causing an infinite re-render loop.

---

## 9. Configuration

| Env var | Default | Notes |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | — | Required |
| `AZURE_OPENAI_ENDPOINT` | — | Required |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Chat model deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-small-1` | Must match Azure deployment name exactly |
| `POSTGRES_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/ecomm_ops` | |
| `QDRANT_URL` | `http://localhost:6333` | |
| `QDRANT_COLLECTION` | `incidents` | |
| `LANGFUSE_PUBLIC_KEY` | `""` | Optional — tracing disabled if empty |
| `LANGFUSE_SECRET_KEY` | `""` | Optional |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Optional — override for self-hosted Langfuse |
| `API_SECRET_KEY` | `change-me` | Auth skipped in dev when value is `change-me` |
| `FRONTEND_URL` | `http://localhost:3000` | CORS allowed origin |

---

## 10. Exception Handling

| Exception | HTTP | Raised when |
|---|---|---|
| `GraphNotInitializedError` | 503 | Route called before `init_compiled_graph()` at startup |
| `ActionExecutionError` | 500 | `graph.ainvoke(Command(resume=...))` fails in `/actions/approve` |
| `ApprovalResumeError` | 500 | Graph resume fails in `/actions/decline` |
| `IncidentQueryError` | 500 | DB failure in `/incidents` |
