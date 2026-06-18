# Implementation Plan — AI E-commerce Operations Brain

## Overview

This plan divides implementation into 6 phases. Each phase produces a working, demonstrable increment. Later phases build on earlier ones without requiring rewrites.

**Total estimated phases**: 6  
**Development approach**: Backend-first, agent-by-agent, tests alongside implementation  
**Key constraint**: Human-in-the-Loop (HITL) via Temporal is infrastructure-heavy — defer to Phase 4

---

## Phase 1 — Foundation & Infrastructure
**Goal**: Running project skeleton with all infrastructure services healthy

### 1.1 Repository & Project Scaffold
- [ ] Initialize `pyproject.toml` with all backend dependencies
- [ ] Initialize Next.js frontend with TypeScript, Tailwind, shadcn/ui
- [ ] Create `docker-compose.yml` with: PostgreSQL, Qdrant, Redis, Temporal server + UI
- [ ] Create `docker-compose.dev.yml` with hot-reload mounts
- [ ] Create `Makefile` with targets: `make up`, `make dev`, `make test`, `make eval`, `make seed`
- [ ] Create `.env.example` with all required environment variables

### 1.2 Backend Core
- [ ] `core/config.py` — Pydantic `BaseSettings` for all env vars
- [ ] `core/llm.py` — `AzureChatOpenAI` + `AzureOpenAIEmbeddings` factory functions
- [ ] `core/observability.py` — Langfuse + LangSmith callback setup
- [ ] `db/postgres.py` — Async SQLAlchemy engine, session factory, lifespan hook
- [ ] `db/qdrant.py` — Qdrant async client, collection initialization
- [ ] `db/redis.py` — Redis async client setup
- [ ] `main.py` — FastAPI app factory with lifespan, CORS, middleware

### 1.3 Database Schema & Migrations
- [ ] Alembic setup + initial migration
- [ ] Tables: `incidents`, `incident_actions`, `daily_sales`, `products`, `inventory`, `campaigns`, `support_tickets`

### 1.4 Seed Data Generation
- [ ] `data/seed/generate_seed.py` — Creates 90 days of realistic sales data
- [ ] Deterministic "bad yesterday" scenario embedded in seed
- [ ] Load seed on startup if tables are empty

**Deliverable**: `docker-compose up` brings up all services; FastAPI returns `200` on `/health`; Postgres tables created and seeded.

---

## Phase 2 — Data Layer & Mock Repositories
**Goal**: All domain data accessible via typed repository interfaces

### 2.1 Domain Models
- [ ] `models/domain.py` — Pydantic models: `DailyRevenue`, `OrderVolume`, `ProductSales`, `RegionalSales`, `AnomalyResult`, `StockLevel`, `StockoutEvent`, `CampaignMetric`, `ChannelPerformance`, `TicketVolumeSummary`, `RefundRateSummary`, `ComplaintTheme`

### 2.2 Repository Interfaces
- [ ] `repositories/interfaces.py` — Protocol definitions for `ISalesRepository`, `IInventoryRepository`, `IMarketingRepository`, `ISupportRepository`

### 2.3 Mock Implementations
- [ ] `repositories/mock/sales.py` — Reads from seed JSON; returns typed domain models
- [ ] `repositories/mock/inventory.py`
- [ ] `repositories/mock/marketing.py`
- [ ] `repositories/mock/support.py`

### 2.4 Postgres Implementations (stub + pluggable)
- [ ] `repositories/postgres/sales.py` — SQLAlchemy queries matching same interface
- [ ] `repositories/postgres/inventory.py`
- [ ] `repositories/postgres/marketing.py`
- [ ] `repositories/postgres/support.py`

### 2.5 Repository Factory
- [ ] `repositories/factory.py` — Returns mock or postgres impl based on `REPO_BACKEND` env var

**Deliverable**: All repository interfaces tested with unit tests; mock data returns realistic values for "yesterday" scenario.

---

## Phase 3 — LangGraph Core & Specialist Agents
**Goal**: Full diagnostic query ("Why did sales drop yesterday?") produces a coherent answer

### 3.1 LangGraph State
- [ ] `graph/state.py` — `OpsState` TypedDict with all fields

### 3.2 LangChain Tools
- [ ] `tools/sales_tools.py` — 6 tools wrapping `ISalesRepository` methods
- [ ] `tools/inventory_tools.py` — 5 tools wrapping `IInventoryRepository` methods
- [ ] `tools/marketing_tools.py` — 5 tools wrapping `IMarketingRepository` methods
- [ ] `tools/support_tools.py` — 4 tools wrapping `ISupportRepository` methods

### 3.3 Specialist Agents
Each agent is implemented as a LangGraph ReAct agent (`create_react_agent`) with domain-specific tools and a system prompt:

- [ ] `agents/intent_router.py` — Structured output: classifies query type + domains + time range
- [ ] `agents/sales_agent.py` — Sales domain ReAct agent
- [ ] `agents/inventory_agent.py` — Inventory domain ReAct agent
- [ ] `agents/marketing_agent.py` — Marketing domain ReAct agent
- [ ] `agents/support_agent.py` — Support domain ReAct agent

### 3.4 Reflection Agent
- [ ] `agents/reflection_agent.py` — Deterministic checks + confidence scoring + gap detection

### 3.5 LangGraph Workflow (diagnostic path only)
- [ ] `graph/nodes.py` — `route_intent`, `run_*_agent`, `run_reflection`, `synthesize_findings`, `format_response` nodes
- [ ] `graph/edges.py` — Conditional edges: parallel dispatch, reflection loop guard, action vs diagnostic branch
- [ ] `graph/workflow.py` — `StateGraph` builder; compile with `MemorySaver` checkpointer

### 3.6 FastAPI Chat Endpoint
- [ ] `api/routes/chat.py` — `POST /chat` (sync), `WS /chat/stream` (streaming tokens via WebSocket)
- [ ] `api/deps.py` — Repository factory DI, graph runner DI

**Deliverable**: `POST /chat` with `"Why did sales drop yesterday?"` returns a structured root cause analysis identifying stockouts + campaign pause as root causes.

---

## Phase 4 — Memory System
**Goal**: Long-term memory enables "What did we do last time?" queries

### 4.1 Episodic Memory (Qdrant)
- [ ] `memory/episodic.py`:
  - `store_incident(incident: IncidentRecord)` — embed + upsert to Qdrant + Postgres
  - `retrieve_similar_incidents(query_text: str, top_k: int) -> list[PastIncident]`
  - `store_action_outcome(incident_id, action, outcome)`

### 4.2 Working Memory (Redis)
- [ ] `memory/working.py`:
  - `save_session_context(session_id, context)`
  - `get_session_context(session_id) -> SessionContext | None`
  - `clear_session(session_id)`

### 4.3 Memory Agent
- [ ] `agents/memory_agent.py` — Tools for retrieval + storage; integrated into graph as `retrieve_memory` and `store_incident` nodes

### 4.4 Structured Incident Log (Postgres)
- [ ] `memory/structured.py` — CRUD operations on `incidents` and `incident_actions` tables
- [ ] `api/routes/incidents.py` — `GET /incidents`, `GET /incidents/{id}` — incident history API

### 4.5 Graph Integration
- [ ] Wire `retrieve_memory` node after reflection
- [ ] Wire `store_incident` node after action execution / final response
- [ ] Multi-turn context: load from Redis at graph start

**Deliverable**: `POST /chat` with `"What did we do last time this happened?"` returns 2–3 past incident summaries with actions taken and outcomes.

---

## Phase 5 — Action Agent & HITL (Temporal)
**Goal**: Action queries propose, approve, and execute changes end-to-end

### 5.1 Action Models
- [ ] `models/actions.py` — `ProposedAction`, `ApprovedAction`, `ActionResult` Pydantic models

### 5.2 Action Tools
- [ ] `tools/action_tools.py` — `restock_product`, `apply_discount`, `pause_campaign`, `resume_campaign`, `create_support_ticket` (mock implementations that log to Postgres)

### 5.3 Action Agent
- [ ] `agents/action_agent.py` — Reads agent findings from state; proposes parameterized actions with justifications

### 5.4 Temporal Infrastructure
- [ ] `hitl/workflows.py` — `ActionApprovalWorkflow`: start → wait for signal (24h timeout) → execute approved → store outcomes
- [ ] `hitl/activities.py` — `execute_action`, `store_outcome`, `notify_frontend` Temporal activities
- [ ] `hitl/worker.py` — Temporal worker runner (started as a separate process/thread)
- [ ] `hitl/approval_bridge.py` — `send_approval_request()` (Temporal → Redis pub/sub → WebSocket) and `receive_decision()` (FastAPI → Temporal signal)

### 5.5 HITL Graph Nodes
- [ ] `graph/nodes.py`: `propose_actions` node, `hitl_checkpoint` node, `execute_actions` node
- [ ] `graph/edges.py`: branch on `intent.query_type == ACTION`; branch on `approved` vs `rejected`

### 5.6 FastAPI Actions API
- [ ] `api/routes/actions.py` — `GET /actions/pending`, `POST /actions/approve`

### 5.7 Frontend — Approval UI
- [ ] `components/approval/ApprovalQueue.tsx` — Polls `GET /actions/pending`
- [ ] `components/approval/ApprovalModal.tsx` — Per-action approve/reject with justification display
- [ ] `components/approval/ActionCard.tsx` — Single action display component
- [ ] `hooks/useApprovals.ts` — Approval state management
- [ ] `store/approvalStore.ts` — Zustand store for approval queue
- [ ] `/approvals` page

**Deliverable**: `POST /chat` with `"Fix the problem."` triggers Temporal workflow; frontend shows approval modal; approving restocks/resumes executes the actions; confirmation returned.

---

## Phase 6 — Frontend, Observability & Evaluation
**Goal**: Complete, polished system with full observability and automated evaluation

### 6.1 Frontend — Chat Interface
- [ ] `components/chat/ChatInterface.tsx` — WebSocket connection, streaming display, session handling
- [ ] `components/chat/MessageBubble.tsx` — User / assistant message styling
- [ ] `components/chat/AgentTrace.tsx` — Collapsible per-agent reasoning accordion
- [ ] `components/chat/StructuredResponse.tsx` — Root cause cards, recommendation list, action badges
- [ ] `hooks/useChat.ts` — WebSocket message state + send
- [ ] `hooks/useWebSocket.ts` — Reconnect logic
- [ ] `store/chatStore.ts` — Message thread, session state

### 6.2 Frontend — Dashboard & Incidents
- [ ] `components/dashboard/MetricCard.tsx` — KPI tiles (revenue, orders, complaints)
- [ ] `components/dashboard/IncidentTimeline.tsx` — Past incident list
- [ ] `components/dashboard/AgentStatusPanel.tsx` — Live agent execution status
- [ ] `/dashboard` and `/incidents` pages

### 6.3 Langfuse Integration
- [ ] Wrap every agent LLM call with `LangfuseCallback`
- [ ] Tag traces by agent name, session ID, query type
- [ ] Add custom spans for reflection confidence scores and memory retrieval scores

### 6.4 LangSmith Integration
- [ ] Confirm `LANGCHAIN_TRACING_V2` is active in all environments
- [ ] Create named project `ecomm-ops-brain` in LangSmith
- [ ] Annotate key chains for dataset creation

### 6.5 DeepEval Evaluation Suite
- [ ] `tests/eval/test_cases.json` — 10+ golden test cases covering:
  - Diagnostic accuracy (root cause precision)
  - Memory recall (correct past incident retrieval)
  - Action proposal quality (relevant, justified actions)
  - Hallucination checks (no invented metrics)
- [ ] `tests/eval/evaluate.py` — DeepEval runner with `AnswerRelevancyMetric`, `FaithfulnessMetric`, `HallucinationMetric`, `ContextualRecallMetric`
- [ ] `make eval` target runs DeepEval suite and prints report

### 6.6 Unit & Integration Tests
- [ ] `tests/unit/test_intent_router.py` — Tests for all query type classifications
- [ ] `tests/unit/test_reflection_agent.py` — Confidence scoring, gap detection
- [ ] `tests/unit/test_memory_agent.py` — Store + retrieve round-trip (mocked Qdrant)
- [ ] `tests/integration/test_graph_diagnostic.py` — Full graph: diagnostic path
- [ ] `tests/integration/test_graph_action.py` — Full graph: action path with mocked Temporal
- [ ] `tests/integration/test_graph_memory.py` — Full graph: memory retrieval path

### 6.7 Documentation
- [ ] `README.md` — Setup, running instructions, demo script
- [ ] `CLI.md` — Available make commands and API endpoints
- [ ] Inline docstrings on all public agent/tool functions

**Deliverable**: All 3 core scenarios fully demonstrable; DeepEval suite passes with ≥0.7 on all metrics; Langfuse dashboard shows traces.

---

## Environment Variables Reference

```bash
# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# PostgreSQL
POSTGRES_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ecomm_ops

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=incidents

# Redis
REDIS_URL=redis://localhost:6379

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_TASK_QUEUE=ops-brain-queue

# Langfuse
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=ecomm-ops-brain

# App
REPO_BACKEND=mock          # mock | postgres
API_SECRET_KEY=            # for Bearer token auth
FRONTEND_URL=http://localhost:3000
```

---

## Dependencies Reference

### Backend (`pyproject.toml`)

```toml
[project]
name = "ecomm-ops-brain-backend"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
  # API
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "python-multipart>=0.0.9",

  # LangChain / LangGraph
  "langchain>=0.3",
  "langchain-openai>=0.2",
  "langchain-community>=0.3",
  "langgraph>=0.2",
  "langsmith>=0.1",

  # Azure OpenAI
  "openai>=1.40",

  # Data / DB
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "qdrant-client>=1.10",
  "redis>=5.0",

  # HITL
  "temporalio>=1.6",

  # Observability
  "langfuse>=2.0",
  "deepeval>=0.21",

  # Models
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "pytest-mock>=3.14",
]
```

### Frontend (`package.json`)

```json
{
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zustand": "^4.5",
    "tailwindcss": "^3.4",
    "@radix-ui/react-dialog": "^1.1",
    "@radix-ui/react-accordion": "^1.2",
    "class-variance-authority": "^0.7",
    "clsx": "^2.1",
    "lucide-react": "^0.400"
  },
  "devDependencies": {
    "typescript": "^5.5",
    "@types/node": "^20",
    "@types/react": "^19",
    "eslint": "^9",
    "eslint-config-next": "^15"
  }
}
```

---

## Demo Script (for presentation)

```
Step 1 — Diagnostic Query
  User: "Why did sales drop yesterday?"
  System: [shows parallel agent execution]
           [Sales: -35% revenue, -28% orders]
           [Inventory: Products A, B, C out of stock all day]
           [Marketing: Paid search campaign paused at 09:00]
           [Support: 2.3x complaint volume, "out of stock" theme]
           [Reflection: confidence 0.88]
           [Memory: 2 similar past incidents found]
           → "Root cause: Top 3 products were out of stock while the
              primary paid search campaign was paused, removing both
              supply and acquisition simultaneously."

Step 2 — Action Query
  User: "Fix the problem."
  System: [Action Agent proposes 3 actions]
           [HITL: approval modal appears in frontend]
  User: [approves restock actions, rejects campaign resume]
  System: [Temporal executes approved actions]
           → "Restocked Product A (500 units) and Product B (300 units).
              Campaign resume was skipped per your decision.
              Actions logged. Estimated recovery: 24–48 hours."

Step 3 — Memory Query
  User: "Did discounts help last time?"
  System: [Memory Agent: Qdrant retrieval → 2 matches]
           → "Feb 03, 2025: Applied 10% discount on affected SKUs.
              Recovery took 3 days; margin impact noted.
              Recommendation: prioritize restock over discount based on
              faster recovery observed in Nov 2024 incident."
```
