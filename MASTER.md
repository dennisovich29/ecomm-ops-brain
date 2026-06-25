# Ecomm Ops Brain — Complete Technical Reference

> Everything you need to understand, explain, and answer cross-questions about this project.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack — Why Each Was Chosen](#3-technology-stack--why-each-was-chosen)
4. [FastAPI — The API Layer](#4-fastapi--the-api-layer)
5. [LangGraph — The Orchestration Engine](#5-langgraph--the-orchestration-engine)
6. [LangChain — The Agent Framework](#6-langchain--the-agent-framework)
7. [Azure OpenAI — LLM and Embeddings](#7-azure-openai--llm-and-embeddings)
8. [PostgreSQL — Relational Store](#8-postgresql--relational-store)
9. [Qdrant — Vector Store](#9-qdrant--vector-store)
10. [Next.js — The Frontend](#10-nextjs--the-frontend)
11. [The LangGraph Workflow — Every Node Explained](#11-the-langgraph-workflow--every-node-explained)
12. [Agent Designs in Depth](#12-agent-designs-in-depth)
13. [HITL — Human-in-the-Loop](#13-hitl--human-in-the-loop)
14. [Memory Architecture](#14-memory-architecture)
15. [SSE Streaming — How It Works](#15-sse-streaming--how-it-works)
16. [Repository Pattern](#16-repository-pattern)
17. [Observability — Langfuse](#17-observability--langfuse)
18. [Key Design Decisions — Why X Over Y](#18-key-design-decisions--why-x-over-y)
19. [Concepts You Should Be Able to Explain](#19-concepts-you-should-be-able-to-explain)
20. [Alternative Frameworks — Context](#20-alternative-frameworks--context)
21. [Documentation Map](#21-documentation-map)

---

## 1. What This Project Is

Ecomm Ops Brain is a **multi-agent AI system** that acts as an intelligent operations manager for an e-commerce business. Instead of querying dashboards manually, an operator types a natural language question and the system:

1. Figures out what the question is asking (intent classification)
2. Dispatches specialist AI agents to investigate relevant data in parallel (sales, inventory, marketing, support)
3. Scores its own confidence, identifies gaps, and re-investigates if needed
4. Pulls in context from similar past incidents stored in a vector database
5. Synthesizes all findings into a root cause analysis using GPT-4o
6. Proposes concrete corrective actions grounded in real database IDs
7. Pauses and asks the human to approve before executing anything
8. Executes approved actions and stores the incident for future memory

The key design principle: **no action executes without human approval**. The system investigates, reasons, and proposes — humans decide.

---

## 2. System Architecture

> Mermaid diagrams for all layers are in **`README.md`** (overview) and **`docs/internals.md`** (full detail — 12 diagrams covering every node, edge, data flow, HITL cycle, and startup order).

The system has five runtime layers:

```
Browser  →  Next.js :3000  →  FastAPI :8000  →  LangGraph (13 nodes)
                                                      │
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                             Azure OpenAI      PostgreSQL :5432    Qdrant :6333
                           (GPT-4o + embeds)  (ops data +         (incident
                                               checkpoints)        vectors)
```

**All browser traffic goes through the Next.js proxy at `/api/*`.** The browser never contacts FastAPI directly. This eliminates CORS issues — the browser only ever talks to Next.js (same origin), and Next.js forwards requests server-side to FastAPI.

---

## 3. Technology Stack — Why Each Was Chosen

| Layer | Technology | Version | Why This, Not X |
|---|---|---|---|
| Backend API | FastAPI | ≥ 0.115 | Native async, automatic OpenAPI docs, Pydantic integration. Over Flask (sync-first, no async) and Django (too heavyweight for an AI API) |
| Orchestration | LangGraph | ≥ 1.0 | Stateful graph with built-in checkpointing, `interrupt()` for HITL, parallel dispatch, cycle detection. Over plain LangChain LCEL (no state, no HITL primitives) and CrewAI (less control over graph topology) |
| Agent Framework | LangChain | ≥ 1.0 | `create_agent` (v1 API), `with_structured_output`, tool decoration, callbacks, first-class middleware. Over custom from-scratch (reinventing the wheel) |
| LLM | Azure OpenAI GPT-4o | API 2024-10-21 | Same OpenAI API surface but enterprise-grade: private endpoints, no data leaves tenant, compliance. Over OpenAI direct (data residency concerns) |
| Embeddings | Azure text-embedding-3-small-1 | — | 1536-dim, excellent semantic quality, same Azure endpoint. Over ada-002 (older, lower quality) |
| Vector DB | Qdrant | v1.9.2 | High-performance cosine similarity, async Python client, payloads stored alongside vectors. Over Pinecone (external SaaS, cost), pgvector (slower for pure vector search), ChromaDB (not production-grade) |
| Relational DB | PostgreSQL 16 | + asyncpg | Industry standard, supports LangGraph checkpointer, excellent async driver (asyncpg), JSON arrays. Over MySQL (less rich types), SQLite (not production) |
| ORM | SQLAlchemy | ≥ 2.0 async | Async sessions, type safety, parameterized queries preventing SQL injection. Over raw asyncpg (verbose, no injection protection) |
| LG Checkpoint | langgraph-checkpoint-postgres | ≥ 2.0 | Persists full OpsState to Postgres — HITL state survives restarts. Over MemorySaver (in-memory, lost on restart) |
| Frontend | Next.js 15 App Router | — | SSR, proxy API routes (eliminate CORS), excellent SSE support. Over CRA (no SSR, no proxy), Vite (no server-side proxy) |
| State (FE) | Zustand | — | Minimal boilerplate, session-keyed state, no Provider hell. Over Redux (heavy), React Context (re-render issues) |
| Observability | Langfuse | ≥ 2.0 | LLM-native tracing — traces every agent call, tool call, token count. Over generic APM tools that don't understand LLM chains |
| Runtime | Python 3.12 | — | Latest stable, best asyncio performance, required by LangGraph 1.0 |
| Packaging | pyproject.toml + hatchling | — | Modern Python packaging standard. Over setup.py (legacy) |
| Package installer | uv | latest | 10-20× faster than pip, resolves and installs in seconds. Drops in as a pip replacement — same `pyproject.toml`, no lockfile required. Over pip (slow), Poetry (different project format) |
| Frontend pkg mgr | pnpm | 10.33.2 | Faster than npm, content-addressable store (deduplicates packages), strict dependency isolation. Over npm (slow, hoisting issues), yarn (less efficient) |

---

## 4. FastAPI — The API Layer

### What FastAPI is

FastAPI is an **async Python web framework** built on:
- **Starlette** — the ASGI web toolkit underneath
- **Pydantic** — for automatic request/response validation and serialization
- **asyncio** — Python's native async event loop

### ASGI vs WSGI

Traditional Python web frameworks (Flask, Django) use **WSGI** (Web Server Gateway Interface) — they handle one request per thread synchronously. While a request waits for a DB query, the thread blocks.

FastAPI uses **ASGI** (Asynchronous Server Gateway Interface). With `async def` handlers and `await`, a single thread can handle thousands of concurrent requests — while one request waits for OpenAI to respond, the event loop switches to processing another request. This is critical here because every request involves multiple LLM calls that take seconds each.

### How endpoints are defined

```python
@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,       # Pydantic validates: content 1-2000 chars, valid session_id
    graph=Depends(get_graph),   # dependency injection — get compiled LangGraph
) -> StreamingResponse:
    ...
```

**`Depends()`** is FastAPI's dependency injection. `get_graph` is called once per request and injects the compiled LangGraph instance. `verify_token` is another dependency that checks the `Authorization` header.

### Pydantic request models

```python
class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    session_id: str
```

FastAPI automatically validates incoming JSON against this. If `content` is missing or too long, FastAPI returns a 422 before the handler even runs.

### StreamingResponse for SSE

```python
return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
)
```

`StreamingResponse` takes an async generator and sends each yielded chunk immediately as it's produced. `media_type="text/event-stream"` tells the browser this is an SSE stream.

### Lifespan events

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_qdrant()
    init_compiled_graph(checkpointer)  # compile LangGraph once at startup
    yield                               # app runs here
    await flush_langfuse()             # cleanup on shutdown
```

`lifespan` is the modern FastAPI way to run startup and shutdown code. It replaces the old `@app.on_event("startup")` pattern.

---

## 5. LangGraph — The Orchestration Engine

### What LangGraph is

LangGraph is a library built on top of LangChain for building **stateful, multi-agent workflows as directed graphs**. Every node is a function. Edges define the control flow. State is a TypedDict that flows through the graph and gets updated at each node.

Think of it as a finite state machine where:
- **Nodes** = processing steps (calling an LLM, querying a DB, reflecting on results)
- **Edges** = routing decisions (conditional or unconditional)
- **State** = the shared data structure that all nodes read from and write to

### Why LangGraph over alternatives

| Alternative | Problem |
|---|---|
| Plain LCEL (LangChain Expression Language) | Chains are stateless — can't persist state between calls, no native HITL |
| CrewAI | Less flexible graph topology, harder to implement custom reflection loops |
| AutoGen | Microsoft-centric, different philosophy (multi-agent conversation vs stateful graph) |
| Custom orchestration | Would need to rebuild checkpointing, interrupt handling, fan-out/fan-in from scratch |

### The StateGraph

```python
builder = StateGraph(OpsState)
builder.add_node("route_intent", node_route_intent)
builder.add_conditional_edges("route_intent", edge_dispatch_agents, {...})
builder.compile(checkpointer=checkpointer)
```

`StateGraph` takes a TypedDict class (`OpsState`) as its state schema. Every node function receives the full current state and returns a **partial dict** — only the keys it wants to update. LangGraph merges the partial dict into the state using **reducers**.

### Reducers

Most state fields use simple assignment (last write wins). `messages` uses the `add_messages` reducer:

```python
messages: Annotated[list, add_messages]
```

`add_messages` appends new messages instead of replacing. This is how conversation history accumulates without you manually managing the list.

### Parallel dispatch (fan-out / fan-in)

When `edge_dispatch_agents` returns a **list** of node names:

```python
def edge_dispatch_agents(state) -> list[str]:
    return ["run_sales_agent", "run_inventory_agent", "run_marketing_agent", "run_support_agent"]
```

LangGraph runs all four nodes **concurrently** (fan-out). They all write to different state keys (`sales_findings`, `inventory_findings`, etc.) so there are no write conflicts. LangGraph waits for all of them to complete before running the next node (`run_reflection`) — this is the fan-in.

**Why this matters:** Without parallelism, 4 agents × ~3 seconds each = 12 seconds. With parallelism, it's ~3 seconds total.

### The `interrupt()` primitive

```python
decision = interrupt({"proposed_actions": proposed})
```

When `interrupt()` is called:
1. LangGraph serializes the entire current `OpsState` to the checkpointer (PostgreSQL)
2. Graph execution stops
3. The `graph.astream()` call in the API route terminates
4. `graph.aget_state(config).next` returns non-empty — indicating the graph is paused

Later, when the human approves:
```python
await graph.ainvoke(Command(resume={"approved_action_ids": [...]}), config)
```

`Command(resume=...)` loads the serialized state from the checkpointer and resumes execution from the `interrupt()` call. `interrupt()` returns the value that was passed to `Command(resume=...)`.

**This is not a thread sleeping.** The process doesn't block. The graph is truly stopped and can be resumed hours later, even after a server restart.

### Checkpointing

`AsyncPostgresSaver` is a LangGraph checkpointer that uses PostgreSQL to store graph state. It creates three tables: `checkpoint_blobs`, `checkpoint_migrations`, `checkpoint_writes`.

The **thread_id** is the key:
```python
config = {"configurable": {"thread_id": session_id}}
```

Every turn within the same session uses the same `thread_id`. LangGraph loads the previous checkpoint at the start of each `astream()` call, so conversation history and state carry over between turns automatically.

### stream_mode

```python
async for mode, data in graph.astream(state, config, stream_mode=["values", "messages"]):
```

Two modes simultaneously:
- `"values"` — emits the full state after each node completes. Used to get `final_response` at the end.
- `"messages"` — emits each LLM token as it's generated, with metadata about which node produced it. Used to stream tokens to the frontend in real time.

### LangGraph Studio

LangGraph Studio is the visual debugger for LangGraph graphs. It shows the graph topology with all nodes and edges, which node is currently executing, the full `OpsState` value at each step, and execution history with time-travel debugging (replay from any checkpoint).

For this project: Studio lets you watch the parallel agent fan-out live, inspect `sales_findings` immediately after `run_sales_agent` completes, and see exactly what `node_hitl_checkpoint` received. More useful than print statements for debugging graph topology issues. Available via the LangGraph platform — not required for Docker Compose deployments.

### LangGraph Cloud

LangGraph Cloud is the managed serverless deployment platform for LangGraph graphs. For this project (self-hosted via Docker Compose), it is not used — the `AsyncPostgresSaver` checkpointer handles state persistence. LangGraph Cloud is relevant when a team wants managed infrastructure and auto-scaling without running their own PostgreSQL checkpointer.

### Performance Overhead

LangGraph adds approximately **4ms per request** vs raw LangChain LCEL for state management and checkpointing. In practice this is irrelevant — LLM calls take 1–5 seconds each, so 4ms of orchestration overhead is unmeasurable noise. The async checkpoint writes to PostgreSQL do not block the event loop.

Baseline (production benchmarks, excluding LLM inference): LangChain LCEL pipeline ≈ 10ms/query. LangGraph stateful workflow ≈ 14ms/query.

---

## 6. LangChain — The Agent Framework

### What LangChain provides

LangChain is a framework for building applications with LLMs. In this project it provides:
- `create_agent` — factory for tool-calling agents (LangChain v1, replaced the deprecated `langgraph.prebuilt.create_react_agent`)
- `with_structured_output` — force LLM to return Pydantic-validated JSON
- `ChatPromptTemplate` — prompt templating
- Tool decoration (`@tool`)
- Callbacks (hooks into every LLM call for observability)
- Middleware (`SummarizationMiddleware`, `PIIMiddleware`, `wrap_tool_call`) — first-class `middleware=[]` parameter on `create_agent`

### The Tool-Calling Agent Loop

The underlying pattern — think, call a tool, observe, repeat — comes from the **ReAct** paper (DeepMind/Google, 2022). LangChain's `create_agent` implements this loop:

1. **Think** — LLM reasons about what data it needs
2. **Act** — calls a tool (e.g. `get_daily_revenue`)
3. **Observe** — reads the tool result back into context
4. Repeat until it has enough information to emit a final answer

```
Thought: I should check sales data for 2026-06-18
Action: get_daily_revenue({"date": "2026-06-18"})
Observation: {"revenue": 31525, "order_count": 230, ...}
Thought: Revenue is down 33%. I should also check for anomalies.
Action: detect_sales_anomaly({"date": "2026-06-18"})
Observation: {"is_anomaly": true, "z_score": -2.8, "severity": "high"}
Thought: I have enough data to answer.
Final Answer: { ... structured JSON findings ... }
```

`create_agent` handles this loop automatically. The LLM decides which tool to call, when to call it, and when it has enough information to stop.

> **Why the rename?** In LangGraph v1, `create_react_agent` (from `langgraph.prebuilt`) was deprecated in favour of `create_agent` (from `langchain.agents`). The new API offers a simpler interface and adds first-class middleware support. The underlying loop is identical — LangChain just dropped "ReAct" from the function name.

### Tools

A LangChain tool is a Python function with a description that the LLM reads to decide when to use it:

```python
@tool
def get_daily_revenue(date: str) -> dict:
    """Get total revenue, order count, and DoD/WoW comparisons for a given date (YYYY-MM-DD)."""
    return repo.get_daily_revenue(date)
```

**The description is critical.** The LLM uses it to decide which tool to call. A vague description leads to wrong tool selection.

### `with_structured_output`

```python
structured_llm = llm.with_structured_output(IntentOutput)
result: IntentOutput = await chain.ainvoke({"query": user_query})
```

This forces the LLM to return JSON that matches a Pydantic model. Under the hood, LangChain passes the Pydantic schema to the LLM as a JSON schema constraint (using OpenAI's function calling / response format features). The result is a fully validated Python object — no JSON parsing, no hallucinated extra fields.

### Middleware

LangChain v1 middleware is a first-class `middleware=[]` parameter on `create_agent`. Each middleware runs hooks around every LLM call inside the agent loop. All imports come from `langchain.agents.middleware`.

**`SummarizationMiddleware(model=llm, trigger=("tokens", 2000), keep=("messages", 20))`**
- When the agent's conversation history exceeds 2,000 tokens, it uses the same LLM to summarize older messages, keeping only the last 20
- `model=` is required — it's the LLM used to generate the summary
- Why: Agent loops can run 5–10 tool calls deep. Each observation adds tokens. Without summarization, a long investigation could overflow the context window.
- Applied to all four specialist agents

**`PIIMiddleware("email", strategy="redact", apply_to_input=True)` / `PIIMiddleware("phone_number", detector=_PHONE_REGEX, strategy="redact", apply_to_input=True)`**
- Scans incoming messages for emails/phone numbers and replaces them with `[REDACTED_EMAIL]` / `[REDACTED_PHONE_NUMBER]` before they reach the LLM
- `phone_number` is not a built-in type — a custom regex detector is passed via `detector=`
- `apply_to_input=True` means it checks user messages; `apply_to_output=True` would also scrub LLM responses
- Applied **only to the support agent** because support tickets contain real customer contact details
- Built-in PII types: `email`, `credit_card`, `ip`, `mac_address`, `url`

**`wrap_tool_call` / `resilient_tool_call`**
- A custom middleware created with `@wrap_tool_call` that catches any exception thrown by a tool and returns a graceful error `ToolMessage` instead of crashing the agent
- This keeps the agent running when a DB query fails — the LLM receives the error text and can continue reasoning with partial data
- Applied to all four specialist agents

```python
# How agents are created (from app/agents/sales_agent.py):
from langchain.agents import create_agent
from app.agents.middleware import agent_middleware

def get_sales_agent():
    llm = get_chat_llm()
    return create_agent(
        model=llm,
        tools=SALES_TOOLS,
        system_prompt=_SYSTEM,
        middleware=agent_middleware(llm),   # [SummarizationMiddleware, resilient_tool_call]
    )

# Support agent additionally gets PII middleware:
# middleware=support_middleware(llm)  →  [PIIMiddleware("email"), PIIMiddleware("phone_number"), SummarizationMiddleware, resilient_tool_call]
```

### Callbacks

LangChain callbacks are hooks that fire at every LLM event:
- `on_llm_start` — before an LLM call
- `on_llm_new_token` — for each streamed token
- `on_llm_end` — after completion
- `on_tool_start` / `on_tool_end` — around tool calls

Langfuse provides a `CallbackHandler` that implements all these hooks and sends the data to the Langfuse server for tracing. We pass it in the `config`:

```python
config = {"callbacks": [langfuse_handler]}
await agent.ainvoke(input, config=config)
```

### LangChain 1.0 + LangGraph 1.0 — Release Context (October 2025)

LangChain 1.0 and LangGraph 1.0 reached stable, LTS release together in October 2025.

- **`AgentExecutor` is deprecated** and in maintenance mode until December 2026. `create_agent` from `langchain.agents` is the replacement. This project uses `create_agent` — it is the current standard for new projects.
- **LangChain agents now run on LangGraph's engine internally.** When you call `create_agent`, the resulting executor uses LangGraph's `StateGraph` under the hood. LangChain and LangGraph are complementary layers, not competitors — LangChain provides the integration and tool ecosystem; LangGraph provides the execution and orchestration engine.
- **`create_react_agent` from `langgraph.prebuilt` is also deprecated.** It was renamed `create_agent` in `langchain.agents` with a cleaner interface and first-class `middleware=[]` support. The underlying tool-calling loop is identical.

---

## 7. Azure OpenAI — LLM and Embeddings

### GPT-4o

Used for:
- Intent classification (structured output)
- All 4 specialist agent tool-calling loops
- Synthesis (root cause analysis)
- Action proposal (grounded action generation)
- General conversational response

GPT-4o is OpenAI's fastest and most cost-efficient model in the GPT-4 family. API version `2024-10-21` is the deployment version — this matters for Azure because different API versions expose different features (function calling, response format, etc.).

### text-embedding-3-small-1

Used for episodic memory:
- Converts incident text into a 1536-dimensional vector
- The same model converts query text into a vector at retrieval time
- Cosine similarity between vectors determines semantic similarity

**Embeddings** are numerical representations of text where semantically similar texts have vectors that point in similar directions. "Sales dropped due to stockout" and "Revenue fell because products were out of stock" would have very similar vectors even though they use different words.

**1536 dimensions** means each text is represented as a list of 1536 floating point numbers.

### Why Azure vs OpenAI direct

Azure OpenAI uses the exact same API (same SDK, same models, same endpoints format) but runs in your Azure tenant:
- Data doesn't leave your Azure subscription
- Enterprise SLAs
- Compliance (GDPR, SOC2, HIPAA)
- No rate-limit sharing with other companies
- Can be put behind a private VNet

**Deployment names**: In Azure OpenAI, you deploy a model with a custom name. The deployment name (`text-embedding-3-small-1`) is what you use in API calls — not the model name. This is why the `.env` value must match exactly what you named it in Azure Portal.

---

## 8. PostgreSQL — Relational Store

### What lives in PostgreSQL

Three categories:

**1. Operational data** (read by agent tools)
- `products`, `inventory`, `daily_sales`, `product_daily_sales`, `product_views`
- `regional_sales`, `campaigns`, `campaign_daily_metrics`
- `channel_daily_performance`, `promotions`, `support_tickets`

**2. Incident log** (written by `store_incident`, read by `/incidents` API)
- `incidents` — one row per completed analysis turn
- `incident_actions` — one row per executed action

**3. LangGraph checkpoint tables** (managed entirely by `AsyncPostgresSaver`)
- `checkpoint_blobs` — serialized `OpsState` snapshots
- `checkpoint_migrations` — schema version tracking
- `checkpoint_writes` — write-ahead log for checkpointer

### asyncpg and SQLAlchemy async

**asyncpg** is a pure-Python async PostgreSQL driver. It uses the PostgreSQL binary protocol and is significantly faster than psycopg2 (the standard sync driver) for I/O-bound workloads.

**SQLAlchemy async** wraps asyncpg with the familiar SQLAlchemy ORM/core interface. Async sessions use `await`:

```python
async with get_db_session() as session:
    result = await session.execute(text("SELECT id FROM products"))
```

Why not raw asyncpg? SQLAlchemy provides:
- Parameterized queries (prevents SQL injection automatically)
- Connection pooling management
- Transaction management (commit/rollback)

### Schema creation — SQLAlchemy ORM

Tables are defined as SQLAlchemy 2.0 ORM models in `app/db/models/`. All inherit from `Base(DeclarativeBase)`. `create_tables()` runs at startup:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

`create_all` is idempotent — it only creates tables that don't yet exist. Seed data is in `app/db/seed.py`, which checks `SELECT COUNT(*) FROM products` and skips if the table already has rows (preserving data in the named `pgdata` Docker volume across rebuilds).

Note: repositories use `text()` SQL directly — they are unaffected by the ORM models. The ORM layer is purely for schema management.

### psycopg3 for checkpointer

The `AsyncPostgresSaver` checkpointer uses **psycopg3** (the `psycopg` package, not `psycopg2`). psycopg3 is the modern rewrite with native async support, binary protocol, and pipeline mode. `langgraph-checkpoint-postgres` requires psycopg3 specifically.

So this project uses **two** PostgreSQL drivers: asyncpg for the app's own data, psycopg3 for the LangGraph checkpointer. They use different connection pool configs but connect to the same database.

---

## 9. Qdrant — Vector Store

### What a vector database is

A vector database stores vectors (arrays of floats) and supports fast approximate nearest-neighbor search. Instead of "find rows where name = X", you do "find rows whose vector is most similar to this query vector."

**Why approximate?** Exact nearest-neighbor search in 1536 dimensions requires comparing against every stored vector — O(N). Qdrant uses HNSW (Hierarchical Navigable Small World) graphs for sub-linear approximate search that is accurate enough for practical use.

### Cosine similarity

Two vectors have high cosine similarity when they point in the same direction, regardless of magnitude. Score ranges from -1 (opposite) to 1 (identical).

```
cos(θ) = (A · B) / (|A| × |B|)
```

In this project, `score_threshold=0.5` means only incidents with similarity > 0.5 to the current query are returned. Incidents below 0.5 are considered semantically unrelated.

### PointStruct

Every stored item in Qdrant is a `PointStruct`:
```python
PointStruct(
    id=incident_id,        # UUID string — unique identifier
    vector=[0.12, -0.34, ...],  # 1536 floats — the embedding
    payload={              # arbitrary JSON metadata
        "incident_id": ...,
        "date": ...,
        "query": ...,
        "root_cause": ...,
        "domains": [...],
        "actions_taken": [...]
    }
)
```

You can filter on payload fields in addition to vector similarity — e.g. "find the most similar incident that also involved the inventory domain."

### Why Qdrant over alternatives

| Alternative | Reason not chosen |
|---|---|
| pgvector (PostgreSQL extension) | Slower for pure vector search, no built-in payload filtering at vector search time |
| Pinecone | Fully managed SaaS — external, cost per vector, data leaves infra |
| Weaviate | More complex setup, overkill for this use case |
| ChromaDB | Not production-grade, no async client |
| FAISS | Pure in-memory library, no server, no persistence |

---

## 10. Next.js — The Frontend

### App Router

Next.js 15 uses the App Router (as opposed to the older Pages Router). In App Router:
- `app/` directory is the root
- `app/page.js` → renders at `/`
- `app/api/chat/stream/route.js` → API route at `/api/chat/stream`

### Proxy API routes

The frontend's `/api/*` routes are server-side Next.js API routes that forward requests to FastAPI:

```js
// app/api/chat/stream/route.js
export async function POST(request) {
    const body = await request.json()
    const backendRes = await fetch("http://backend:8000/chat/stream", {
        method: "POST",
        body: JSON.stringify(body),
        headers: { Authorization: `Bearer ${API_SECRET_KEY}` }
    })
    return new Response(backendRes.body, {
        headers: { "Content-Type": "text/event-stream" }
    })
}
```

The browser calls `/api/chat/stream` on Next.js. Next.js calls `http://backend:8000/chat/stream` on the server side. The Docker network makes `backend` resolvable. The browser never sees the FastAPI URL or the API key.

### Zustand state management

Zustand is a minimal React state management library. Unlike Redux, there are no reducers, actions, or dispatchers. It's just a store with getters and setters:

```js
const useStore = create((set) => ({
    messagesBySession: {},
    addMessage: (sessionId, msg) => set((state) => ({
        messagesBySession: {
            ...state.messagesBySession,
            [sessionId]: [...(state.messagesBySession[sessionId] || []), msg]
        }
    }))
}))
```

**Critical pattern**: Selector fallbacks must be applied after `useStore()`:
```js
// WRONG — causes infinite re-renders
const messages = useStore(s => s.messagesBySession[id] || [])  // new [] every render

// CORRECT
const messagesBySession = useStore(s => s.messagesBySession)
const messages = messagesBySession[id] || []  // stable reference
```

---

## 11. The LangGraph Workflow — Every Node Explained

### The complete graph topology

```
START
  └─▶ route_intent
        ├─▶ [GENERAL / no domains] ──────────────────────────────┐
        └─▶ [parallel dispatch]                                   │
              ├─▶ run_sales_agent ──┐                             │
              ├─▶ run_inventory_agent ─▶ run_reflection           │
              ├─▶ run_marketing_agent ─┘     ├─▶ [SUMMARY] ──────┤
              └─▶ run_support_agent          ├─▶ [re_query] ──▶ route_intent (loop)
                                             └─▶ [synthesize]    │
                                                   │              │
                                             retrieve_memory      │
                                                   │              │
                                          synthesize_findings     │
                                                   │              │
                                           store_incident         │
                                                   ├─▶ [action] ─┤
                                                   │              │
                                           propose_actions        │
                                                   │              │
                                          hitl_checkpoint ────────┤
                                                   └─▶ [approved] │
                                                execute_actions   │
                                                        │         │
                                                        └─────────┤
                                                                  ▼
                                                         format_response
                                                                  │
                                                                END
```

### node_route_intent

**What it does:** Calls the intent router LLM to classify the query. Initializes a fresh state for new turns (resets findings, reflection state, action state). On re-query passes (reflection loops), preserves existing findings so only missing domains are re-run.

**Why it's the entry point:** Every query needs to be classified before any agent runs. The classification determines which agents are dispatched and how the rest of the graph routes.

**State written:** `intent`, `active_agents`, `turn_id`, and on fresh turns: all findings/reflection/action fields reset to null/empty.

### node_run_*_agent (×4)

**What they do:** Each runs a `create_agent` tool-calling agent with domain-specific tools. The agent calls tools, observes results, and produces a structured JSON findings dict.

**Why parallel:** All four domains are independent — sales data doesn't affect how inventory data is fetched. Running them in parallel (LangGraph fan-out) reduces total latency from ~12s to ~3s.

**Findings parsing:** Agent output is text. The node tries to extract JSON (`content.find("{")` to `content.rfind("}")`) and falls back to `{"raw": content}` if parsing fails. The `parsed=json|text` log line tells you which happened.

**State written:** `sales_findings`, `inventory_findings`, `marketing_findings`, `support_findings` (each agent writes only its own).

### node_run_reflection

**What it does:** Deterministic Python — no LLM call. Scores confidence by checking which domains have populated findings. Adds corroboration boosts (+0.10 each) when multiple domains tell consistent stories (e.g. stockouts AND sales drop together = more credible).

**Confidence formula:**
```
base = populated_domains / total_requested_domains

boosts (+0.10 each, max +0.30):
  - inventory has stockout_events AND sales has revenue_summary
  - marketing has campaign_issues AND sales has revenue_summary
  - support has complaint_themes AND inventory has stockout_events

confidence = min(base + boosts, 1.0)
```

**Why pure Python here:** Confidence scoring is deterministic logic, not reasoning. Using an LLM here would add latency and cost for no benefit.

**State written:** `gaps_identified`, `confidence_score`, `reflection_notes`, `reflection_passes`.

### node_retrieve_memory

**What it does:** Builds a text representation of the current state (query + findings), embeds it, and searches Qdrant for top-3 semantically similar past incidents with score ≥ 0.5.

**Why after reflection:** Reflection confirms we have enough data to proceed. We want to enrich synthesis with memory context from similar past situations.

**The embedding text is rich:** Including domain findings means the vector captures WHAT happened (revenue drop, stockouts), not just what the user typed. This gives better semantic matches.

**State written:** `similar_incidents` (list of past incidents with `similarity_score`).

### node_synthesize_findings

**What it does:** Calls GPT-4o with: current findings from all agents + past similar incidents + last 3 turns of conversation history. Produces the root cause analysis narrative that becomes the main response.

**Streaming:** This is the ONLY node that streams tokens to the frontend. The `messages` stream mode in `graph.astream()` emits each partial token from this node, filtered by `langgraph_node == "synthesize_findings"`.

**Conversation history injection:** Takes `messages[-6:]` (last 3 turns = 6 messages, alternating Human/AI). This is how follow-up questions work — "why?" after a full analysis knows what "why" refers to.

**State written:** `root_cause_analysis`, `messages` (appends AI response message).

### node_store_incident

**What it does:** Embeds the current state and upserts it to Qdrant. Mirrors to the `incidents` Postgres table as secondary storage.

**Why immediately after synthesis:** This ensures every completed analysis is persisted — regardless of whether the user approves actions, declines them, or it's a pure diagnostic query. The earlier bug was `store_incident` only ran after action execution, so diagnostic queries never stored anything.

**Qdrant is source of truth:** If the Postgres mirror write fails, it logs a WARNING but doesn't fail — Qdrant is what powers the semantic memory retrieval.

**State written:** `current_incident_id`.

### node_propose_actions

**What it does:** Calls GPT-4o with the current findings. Before prompting, fetches all valid `products.id` and `campaigns.id` from DB and injects them into the system prompt. This grounding prevents the LLM from inventing product IDs.

**Why grounding matters:** Without real IDs, the LLM might propose `{"product_id": "wireless-headphones"}` which doesn't exist in the DB. With grounding: `{"product_id": "SKU-001"}` which is the actual key.

**Output validation:** The JSON array is parsed and each element validated against `ProposedAction` (Pydantic). Invalid items are silently dropped.

**State written:** `proposed_actions`.

### node_hitl_checkpoint

**What it does:** Calls `interrupt()` which pauses the graph. On resume, receives the human's decision dict and filters `proposed_actions` to only those with `action_id` in `approved_action_ids`.

**The interrupt/resume cycle** is covered in detail in Section 13.

**State written:** `approved_actions`.

### node_execute_actions

**What it does:** Iterates `approved_actions` and calls `execute_action()` for each. Each action type has its own SQL handler. Results are collected with `success: bool` and `message: str`.

**Why one at a time:** Actions might have dependencies (restock before resume campaign), and individual failures shouldn't stop other actions. Parallel execution would also create race conditions on shared DB state.

**State written:** `executed_actions`.

### node_format_response

**What it does:** Builds the final structured response dict based on `query_type`. Routes to different formatters:
- `GENERAL` → LLM-generated conversational answer (no data)
- `SUMMARY` → renders raw agent findings as markdown tables
- `MEMORY` → lists retrieved similar incidents
- `ACTION/HYBRID` with `executed_actions` → execution summary
- Default → diagnostic response with `root_cause_analysis`

**State written:** `final_response`, `messages` (appends AI message for history).

---

## 12. Agent Designs in Depth

### Intent Router

**Type:** Not a ReAct agent. A single LLM call with structured output.

```python
chain = ChatPromptTemplate | llm.with_structured_output(IntentOutput)
result = await chain.ainvoke({"query": user_query})
```

`IntentOutput` is a Pydantic model. `with_structured_output` uses OpenAI function calling to force the LLM to return exactly this schema.

**`IntentOutput` has 5 fields:**

| Field | Type | Purpose |
|---|---|---|
| `query_type` | str | `DIAGNOSTIC`, `ACTION`, `MEMORY`, `SUMMARY`, `HYBRID`, `GENERAL` |
| `domains` | list[str] | Subset of `[sales, inventory, marketing, support]` |
| `time_range` | TimeRange | `{start: ISO, end: ISO}` |
| `entities` | list[str] | Named products, SKUs, campaigns extracted from query |
| `action_requested` | bool | True only when user explicitly requests an action |

**`action_requested` field:** Critical for correct routing. `HYBRID` queries that span multiple intent types (e.g. diagnosis + summary) should NOT trigger HITL unless the user explicitly asked for something to be done. This boolean prevents "give me a full picture" from showing the action approval card.

**`entities` field:** Named entities extracted from the query — product names, SKU IDs, campaign names. Gives downstream agents awareness of which specific items the user mentioned without requiring the agents to re-parse the original query text.

**Fallback:** If `time_range.start` is empty (user didn't specify a date), defaults to yesterday. This prevents agents from making ambiguous queries to the DB.

### Specialist Agents (Sales / Inventory / Marketing / Support)

Each created with:
```python
from langchain.agents import create_agent

agent = create_agent(
    model=llm,
    tools=DOMAIN_TOOLS,
    system_prompt=_SYSTEM,        # injects the domain-specific instructions
    middleware=agent_middleware(llm),
)
```

`system_prompt=` tells the agent it is the Sales / Inventory / Marketing / Support specialist, sets the investigation protocol (which tools to call, in what order), and defines the output format (structured JSON).

These agents run inside a single LangGraph node invocation — they don't persist their own state across turns. The outer LangGraph graph (`AsyncPostgresSaver`) handles all checkpointing.

**Tool schema matters:** LangChain passes tool descriptions to the LLM as part of the prompt. The LLM reads "Get total revenue and DoD/WoW comparisons for a given date" and knows when to call `get_daily_revenue` vs `detect_sales_anomaly`.

### Reflection Agent

The reflection agent is unusual: **it has no LLM**. It's pure Python that implements a confidence heuristic.

Why this is intentional: Confidence scoring is a deterministic computation. An LLM asked "do you have enough data?" will hallucinate confidence it doesn't have. Pure Python is predictable, fast, and testable.

The **re-query loop** is bounded by `MAX_REFLECTION_PASSES = 3` to prevent infinite loops. On re-query, `edge_dispatch_agents` checks `gaps_identified` and only re-runs agents for missing domains — preserving findings from domains that already succeeded.

### Action Agent

The most safety-critical agent. Two mechanisms prevent bad actions:

1. **Grounding:** Real DB IDs are fetched and injected into the prompt. The LLM can only use IDs that actually exist.

2. **Pydantic validation:** Output is validated against `ProposedAction`:
```python
class ProposedAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str
    parameters: dict
    justification: str
    impact_estimate: str
    reversible: bool = True
```

Items that don't match are dropped. This prevents a badly-formatted LLM response from reaching `execute_actions`.

---

## 13. HITL — Human-in-the-Loop

### The problem HITL solves

AI systems can propose actions confidently and incorrectly. In an e-commerce context, executing the wrong action (pausing a healthy campaign, applying a discount to the wrong product) has real business impact. HITL is the safety gate.

### The full interrupt / resume cycle

```
1. node_propose_actions runs → proposed_actions = [...]

2. node_hitl_checkpoint calls:
   interrupt({"proposed_actions": proposed_actions})
   
3. LangGraph does:
   - Serializes full OpsState to PostgreSQL (checkpoint_blobs)
   - Raises an internal interrupt exception
   - graph.astream() terminates

4. chat.py SSE handler detects interruption:
   snapshot = await graph.aget_state(config)
   if snapshot.next:  # graph is paused
       # send approval_pending SSE event
   
5. Frontend receives:
   {"type": "final_response", "response": {"type": "approval_pending",
    "proposed_actions": [...], "workflow_id": session_id}}
   
6. Frontend renders InlineApprovalCard

7. Operator clicks Approve (selects action checkboxes)

8. Frontend POST /api/actions/approve {approved_action_ids: ["uuid1", "uuid2"]}

9. FastAPI:
   await graph.ainvoke(
       Command(resume={"approved_action_ids": ["uuid1", "uuid2"]}),
       config={"configurable": {"thread_id": session_id}}
   )

10. LangGraph:
    - Loads OpsState from PostgreSQL checkpointer
    - Resumes from the interrupt() call
    - interrupt() returns {"approved_action_ids": ["uuid1", "uuid2"]}
    - node_hitl_checkpoint filters: approved = [a for a in proposed if a.action_id in approved_ids]
    
11. node_execute_actions runs with approved_actions
```

### Why `interrupt()` vs a separate workflow engine

Alternatives like Temporal or Prefect could handle HITL, but they add operational complexity (another service to deploy, another SDK to learn, separate task queues). LangGraph's `interrupt()` achieves the same with:
- No extra services
- State persisted in the same PostgreSQL that's already running
- Resume is a single API call
- Full OpsState is preserved exactly as it was

The trade-off: The HITL window is limited by the checkpointer state retention. If PostgreSQL is wiped, pending approvals are lost.

---

## 14. Memory Architecture

Three distinct memory tiers:

### Tier 1: Conversational Memory (LangGraph Checkpointer)

**Storage:** PostgreSQL `checkpoint_*` tables  
**What's stored:** Full `OpsState` including `messages` list  
**How it works:** `add_messages` reducer appends `HumanMessage + AIMessage` each turn. Since `thread_id = session_id`, LangGraph automatically loads the previous checkpoint at the start of each `astream()` call. The conversation history is in `OpsState.messages`.

**Used in:** `synthesize_findings` injects the last 3 turns (6 messages) into the synthesis prompt as "Conversation history:" context. This makes follow-up questions work — "why?" resolves to "why did the thing described in the previous answer happen."

**No Redis needed:** Earlier versions of this project used Redis for session context. This was removed because LangGraph's own checkpointer already persists state. Adding Redis was redundant.

### Tier 2: Episodic Memory (Qdrant)

**Storage:** Qdrant `incidents` collection  
**What's stored:** Incident vectors + payload (query, root_cause, domains, confidence, actions_taken)  
**How it works:**

*Writing:*
```python
text = "user_query | root_cause[:400] | sales_findings[:200] | ..."
vector = await embeddings.aembed_query(text)
await qdrant.upsert(collection, [PointStruct(id=uuid, vector=vector, payload={...})])
```

*Reading:*
```python
query_vector = await embeddings.aembed_query(current_state_text)
results = await qdrant.search(collection, query_vector, limit=3, score_threshold=0.5)
```

**Why this matters:** If the same problem occurred before, the synthesis node gets to see: what happened, what the root cause was, and what actions were taken. This gives the LLM historical context it wouldn't have otherwise.

**Score threshold 0.5 and query specificity:** Short, vague queries ("were there past issues?") have low cosine similarity to long, domain-rich incident vectors. Use specific vocabulary ("stockout-driven revenue drop with campaign issues") to get above 0.5.

### Tier 3: Structured Memory (PostgreSQL incidents table)

**Storage:** PostgreSQL `incidents` + `incident_actions` tables  
**What's stored:** Queryable incident record — same data as Qdrant payload but in structured form  
**Purpose:** Powers the `GET /incidents` endpoint that populates the frontend incident sidebar. Not used for semantic search.

**Write order:** Qdrant write happens first. Postgres mirror is non-blocking — if it fails, a WARNING is logged but the incident is not lost (it's in Qdrant).

---

## 15. SSE Streaming — How It Works

### What SSE is

**Server-Sent Events (SSE)** is an HTTP protocol for server→client push. The server keeps an HTTP connection open and sends events as they occur. Events have the format:

```
data: {"type": "token", "content": "Revenue"}\n\n
data: {"type": "token", "content": " dropped"}\n\n
data: {"type": "final_response", "response": {...}}\n\n
```

Each event is `data: <json>\n\n` (double newline terminates the event).

### Why SSE over WebSocket

| SSE | WebSocket |
|---|---|
| Unidirectional (server→client) | Bidirectional |
| Standard HTTP, works through proxies | Requires upgrade handshake, some proxies block |
| Simpler client code (EventSource API) | More complex protocol |
| Sufficient for token streaming | Needed for real-time bidirectional (chat apps, games) |

For this use case, the server streams tokens and the client only sends one initial request. SSE is simpler and sufficient.

### How token streaming works end-to-end

```
GPT-4o generates token "Revenue"
  → Azure OpenAI streams it to the LangChain LLM
    → LangChain emits on_llm_new_token callback
      → LangGraph messages stream emits (AIMessageChunk, {langgraph_node: "synthesize_findings"})
        → chat.py event_generator yields:
          f'data: {json.dumps({"type": "token", "content": "Revenue"})}\n\n'
            → FastAPI StreamingResponse sends it
              → Next.js proxy passes it through
                → browser EventSource receives it
                  → useChat.js appends to message being built
                    → React re-renders with updated text
```

### Why only synthesize_findings streams

```python
if mode == "messages":
    msg, meta = data
    if meta.get("langgraph_node") == "synthesize_findings":
        # only stream tokens from this node
```

Other nodes also call LLMs (intent_router, action_agent) but streaming their tokens would be confusing — you'd see the JSON intent classification output appear in the chat. Only the synthesis node produces human-readable text that should be streamed.

### HITL detection after streaming

```python
# After astream() loop finishes:
snapshot = await graph.aget_state(config)
if snapshot.next:  # non-empty means graph is paused at an interrupt
    # send approval_pending event
```

`snapshot.next` is a tuple of node names the graph would execute next. If non-empty, the graph is paused (interrupted). This is how the API detects that it should send an `approval_pending` event instead of a normal `final_response`.

---

## 16. Repository Pattern

### Why a repository pattern

The repository pattern separates **what data you need** from **how you get it**. Agents call `get_daily_revenue(date)` — they don't know or care whether that executes a SQL query, hits an API, or reads a file.

```python
class ISalesRepository(Protocol):
    async def get_daily_revenue(self, date: str) -> DailyRevenue: ...
    async def detect_anomaly(self, date: str) -> AnomalyResult: ...
    # ...

class PostgresSalesRepository:
    async def get_daily_revenue(self, date: str) -> DailyRevenue:
        async with get_db_session() as db:
            row = await db.execute(text("SELECT ..."), {"date": date})
            return DailyRevenue(**row.fetchone())
```

### Protocol (structural subtyping)

Python's `Protocol` (from `typing`) enables **structural subtyping** — "duck typing" but with static type checking. `PostgresSalesRepository` doesn't inherit from `ISalesRepository` — it just implements the same methods. MyPy checks this statically.

This matters for testing: you can create a `MockSalesRepository` that returns fixed data without touching the DB, and inject it without changing any agent code.

### File layout

Repository implementations are flat under `app/repositories/` — no subdirectory:

```
repositories/
├── interfaces.py   # ISalesRepository, IInventoryRepository, IMarketingRepository, ISupportRepository
├── factory.py      # get_sales_repo(), get_inventory_repo(), get_marketing_repo(), get_support_repo()
├── sales.py        # PostgresSalesRepository
├── inventory.py    # PostgresInventoryRepository
├── marketing.py    # PostgresMarketingRepository
└── support.py      # PostgresSupportRepository
```

### Why mock repositories were removed

The mock repos (`v1`) were in-memory Python dicts with hardcoded data. They were useful for initial development but:
- Diverged from real DB schema over time
- Tests passing with mocks but failing with real DB (happened in practice)
- All development now happens with a real Postgres DB via Docker Compose

`v2` (PostgreSQL) is the only backend. This forces all tests to use real queries and real data, which is more reliable.

---

## 17. Observability — Langfuse

### What Langfuse is

Langfuse is an **LLM observability platform** — like Datadog for AI. It records every:
- LLM call (prompt, response, tokens used, latency)
- Tool call (tool name, input, output)
- Agent trace (full reasoning chain)
- Embeddings call

### How it's wired

Two levels of handlers:

**Root handler** (per request): Created in `chat.py`, passed in `config={"callbacks": [root_handler]}` to `graph.astream()`. Captures the top-level trace for the entire turn.

**Node-level handlers**: Created in each node via `get_callbacks(session_id, "sales")`. Passed to individual agent invocations. These appear as sub-spans within the root trace.

### What you see in Langfuse traces

For a full diagnostic query:
```
Turn (root)
  └─▶ intent_router
        └─▶ GPT-4o call (prompt + structured output)
  └─▶ sales_agent
        └─▶ middleware: SummarizationMiddleware (if token threshold hit)
        └─▶ middleware: resilient_tool_call (wraps each tool)
        └─▶ GPT-4o call (think step)
        └─▶ tool: get_daily_revenue
        └─▶ GPT-4o call (observe + think)
        └─▶ tool: detect_sales_anomaly
        └─▶ GPT-4o call (final answer)
  └─▶ [inventory, marketing — same pattern]
  └─▶ synthesis
        └─▶ GPT-4o call (RCA streaming)
```

For the support agent, PII middleware runs first on each input message:
```
  └─▶ support_agent
        └─▶ middleware: PIIMiddleware[email] → redacts emails before LLM sees them
        └─▶ middleware: PIIMiddleware[phone_number] → redacts phone numbers
        └─▶ middleware: SummarizationMiddleware
        └─▶ middleware: resilient_tool_call
        └─▶ GPT-4o call
```

### Why Langfuse over LangSmith

Both are valid. LangSmith is built by the LangChain team and has tighter integration. Langfuse is open-source and can be self-hosted. This project uses **Langfuse only** — configured via `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` in `.env`, wired through explicit `CallbackHandler` instances passed per request. LangSmith is not used.

---

## 18. Key Design Decisions — Why X Over Y

### Why LangGraph `interrupt()` for HITL instead of a task queue

A task queue approach (Celery, Temporal) would: start the graph → pause at action proposal → serialize to queue → wait for external signal → resume. This adds operational complexity (another service, another DB, another deployment concern). LangGraph's `interrupt()` achieves the same with the checkpointer we already have. Trade-off: less visibility into long-running tasks, but adequate for this use case.

### Why `store_incident` always runs after `synthesize_findings`

Original design: `store_incident` only ran after `execute_actions`. Problem: any query that didn't result in approved actions (diagnostics, declined HITL, memory queries) never wrote to Qdrant. The episodic memory was permanently empty.

Fix: `store_incident` runs unconditionally after `synthesize_findings`. `edge_after_synthesis` uses `action_requested` to decide whether to also propose actions. Incident storage and action proposal are now independent.

### Why `action_requested: bool` on Intent instead of just checking `query_type == "ACTION"`

`HYBRID` queries can span multiple intent types. "What's causing the drop and summarize the week's performance" is HYBRID but has no action intent — it should NOT show HITL. Without `action_requested`, every HYBRID query would show the action approval card. The explicit boolean from the intent classifier correctly handles this.

### Why Next.js proxy instead of direct backend calls

Direct calls require: CORS headers on FastAPI, exposing the backend URL to the browser, and exposing `API_SECRET_KEY` in the browser (catastrophic). The proxy: keeps the auth header server-side, single origin for the browser, allows switching backend URLs without frontend changes.

### Why PostgreSQL for LangGraph checkpointing instead of MemorySaver

`MemorySaver` stores state in Python process memory. On server restart, all conversation history and pending HITL approvals are lost. With `AsyncPostgresSaver`:
- Conversation history survives restarts
- HITL interrupts survive restarts (the user can come back and approve later)
- Multiple backend instances can share the same state (horizontal scaling possible)

### Why cosine similarity instead of dot product for Qdrant

Dot product (A · B) is affected by magnitude — longer texts with more words produce larger vectors and would always score higher. Cosine similarity normalizes by magnitude so it measures semantic direction, not text length. For comparing incident descriptions of varying lengths, cosine is the correct metric.

### Industry Evidence — Why LangGraph in Production

Three production deployments validate the LangGraph choice for stateful agent workflows:

**Klarna** (85M users): Customer support agent built on LangGraph. Conditional routing handles issue types, retry logic manages failed API calls, escalation paths route complex cases to human agents. Results: resolution time from 11 min → 2 min (80% reduction), 2.5M conversations handled (equivalent to 700 full-time agents), $40M projected profit improvement, 25% drop in repeat inquiries.

**AppFolio** (property management copilot, Realm-X): Migrated from LangChain to LangGraph specifically for complex workflow management — dynamic few-shot prompting, parallel branch execution, and LangSmith evaluation. Results: 2× improvement in response accuracy after migration, text-to-data feature from 40% → 80%, 10+ hours saved per property manager per week. This migration is the clearest documented evidence that LangChain's linear model hits a ceiling for stateful agent workflows.

**Replit** (full-stack dev assistant): Multi-step agent that plans environments, installs dependencies, writes code, and deploys — a workflow a linear chain fundamentally cannot support. Results: 2–3× speed improvements across agent v2→v3 iterations, agent runs autonomously up to 200 minutes. LangGraph's state management enabled workflow complexity that a linear chain would not.

The consistent pattern: linear, stateless workflows succeed with LangChain LCEL. Workflows with memory, retry loops, conditional branching, or HITL belong in LangGraph. This project is in the latter category across all dimensions.

---

## 19. Concepts You Should Be Able to Explain

### Async Python (asyncio)

Python's event loop. `async def` marks a coroutine. `await` suspends the coroutine and yields control back to the event loop, which can run other coroutines while this one waits. This is cooperative multitasking — not multi-threading, not multi-processing. One thread handles many concurrent I/O-bound operations.

### Structured Output (JSON mode / function calling)

OpenAI models support a "response format" that forces them to output JSON conforming to a schema. LangChain's `with_structured_output(Model)` uses this under the hood — it converts the Pydantic model to a JSON Schema and passes it to the API. The model's output is guaranteed to parse into the Pydantic model. This replaces fragile JSON parsing from free-text output.

### Tool-calling agent patterns

The underlying loop this project uses is the **ReAct** pattern (DeepMind/Google, 2022): Think → Act → Observe → repeat. LangChain v1 implements this via `create_agent` (the successor to the deprecated `create_react_agent`).

Other patterns you should know:
- **Chain-of-Thought:** Think step by step before answering. No tool calls.
- **Plan-and-Execute:** Generate a full plan upfront, then execute each step. LangGraph supports this topology.
- **Reflexion:** LLM self-evaluates after an answer and retries. Similar to our reflection node but LLM-driven (ours is pure Python for predictability).
- **ReAct (what we use):** Interleaves reasoning and tool calls. The LLM only knows what to do next after seeing the previous tool result — more adaptive than a fixed plan.

### Vector embeddings intuition

An embedding model maps text to a point in high-dimensional space. Texts with similar meanings are close together. Training involves learning that "stockout caused revenue drop" and "out-of-stock products reduced sales" should be nearby, while "marketing campaign paused" should be in a different neighborhood. The 1536-dimensional space has enough capacity to capture nuanced semantic relationships.

### LangGraph state reducers

Default state updates replace the value. `add_messages` is a custom reducer that appends. You can write your own reducers — e.g. a reducer that merges dicts, or one that keeps only the last N items. The reducer is specified in the TypedDict annotation: `field: Annotated[type, reducer_function]`.

### Thread ID and multi-tenancy

`thread_id` is LangGraph's session isolation mechanism. Each unique `thread_id` gets its own independent checkpoint. Using `session_id` as `thread_id` means each browser session has completely isolated conversation history. Two users querying at the same time never see each other's state.

### `Command(resume=...)` mechanics

`Command` is a LangGraph primitive for controlling graph execution from outside the graph. `Command(resume=value)` tells the checkpointer: load the state at the last `interrupt()`, inject `value` as the return value of `interrupt()`, and continue execution from that point. The graph has no idea it was ever stopped — it sees a continuous execution from its perspective.

### Pydantic v2 and Settings

Pydantic v2 rewrites validation in Rust (via PyO3), making it 5-50x faster. `BaseSettings` (from `pydantic-settings`) reads values from environment variables and `.env` files. Field names are lowercased and matched to env var names. `@lru_cache` on `get_settings()` ensures the settings are only parsed once per process — not on every request.

### HNSW (Hierarchical Navigable Small World)

The indexing algorithm Qdrant uses. It builds a multi-layer graph where close-together vectors are connected. Searching starts at the top layer (coarse), descends to lower layers (fine), following edges to neighbors. O(log N) search instead of O(N). Trade-off: approximate results, but accuracy is tunable and practically very high for semantic similarity.

### Docker Compose networking

All services in a Compose file are on the same Docker virtual network. Container hostnames equal service names (`postgres`, `qdrant`, `backend`). The backend uses `postgresql+asyncpg://postgres:5432/...` not `localhost:5432` — `localhost` inside a container refers to the container itself, not the host machine. `depends_on` with `condition: service_healthy` waits for healthcheck to pass before starting dependent services.

---

## 20. Alternative Frameworks — Context

### PydanticAI

Released late 2024 by the Pydantic team. An agent framework built entirely around strict type safety. Where LangChain/LangGraph use `TypedDict` or loose dicts, PydanticAI enforces Pydantic v2 validation on every input, output, and tool call result.

Key characteristics:
- Full Pydantic v2 validation throughout — schema mismatches raised at runtime, not silently passed downstream
- Model-agnostic: OpenAI, Anthropic, Gemini, Groq, Mistral
- Dependency injection for services/databases into agents without global state
- Typed tool definitions that auto-generate JSON schemas from Python type hints

**When to use over this stack:** Teams that prioritize strict type safety at every agent boundary, without needing full state machine complexity. Lighter choice for structured output pipelines. Does NOT have LangGraph's persistence, HITL interrupt/resume, or parallel fan-out.

### OpenAI Agents SDK

Released March 2025, OpenAI's production successor to the Swarm prototype. Opinionated multi-agent framework designed for the OpenAI ecosystem.

Key characteristics:
- **Handoffs** between agents are a first-class primitive — agent A delegates to agent B based on task type, without custom routing logic
- **Guardrails** run as parallel validation agents checking inputs/outputs against policies before they reach or leave the primary agent
- Built-in tracing via OpenAI's platform — no separate observability tool needed
- Runs natively on OpenAI models (function calling, structured outputs, Responses API)

**When to use over this stack:** Teams fully committed to OpenAI's model stack who want the simplest multi-agent handoff architecture. Trade-off: vendor lock-in to OpenAI — not practical for Azure deployments, multi-provider setups, or open-source models. No equivalent to LangGraph's `interrupt()`/`Command(resume=...)` HITL primitive.

### LangChain vs LangGraph — Decision Framework

| Criteria | Use LangChain | Use LangGraph |
|---|---|---|
| Workflow type | Linear, stateless, single-pass | Cyclic, stateful, multi-step |
| State management | In-memory or session-scoped is sufficient | Must survive restarts, span multiple turns |
| Control flow | Sequential steps with fixed structure | Conditional branches, retry loops, parallel paths |
| Human-in-the-loop | Not needed | Required or likely |
| Failure recovery | Acceptable to restart from scratch | Must resume from last known-good state |
| Multi-agent | Single agent or simple chain | Multiple specialized agents with shared state |
| Timeline | Prototype / rapid MVP | Production agent with real failure modes |

This project sits firmly in the LangGraph column on every dimension: parallel agent dispatch, bounded re-query loops, episodic memory retrieval, HITL approval gating, and multi-turn conversation persistence all require cyclic state machine semantics. LangChain LCEL alone cannot express any of these patterns.

### LangSmith Fleet (formerly LangSmith)

LangSmith, the observability platform built by the LangChain team, was renamed **LangSmith Fleet** in March 2026 to reflect fleet-level agent management capabilities. This project does **not** use LangSmith/Fleet — it uses **Langfuse** instead (see Section 17). LangSmith Fleet is a valid alternative but requires LangSmith API keys and sends trace data to LangChain's hosted platform. Langfuse is open-source and can be self-hosted.

---

## 21. Documentation Map

All project documentation and what each file is for.

| File | What it contains | Best for |
|---|---|---|
| `README.md` | Project overview, Mermaid architecture diagram, quick start, API endpoints, env vars, project structure | First look at the project |
| `docs/internals.md` | 12 Mermaid diagrams covering every node, edge, state field, HITL cycle, memory layer, startup order, and observability flow | Demo walkthroughs, understanding data flow visually |
| `docs/architecture.md` | System context diagram, component diagram, Docker Compose diagram, tech stack table | High-level structural overview |
| `docs/sequence.md` | Sequence diagrams for all 5 query types (Diagnostic, Action, Memory, Summary, HITL resume) | Explaining request/response flow per scenario |
| `docs/lld.md` | API contracts, DB schema, tool signatures, node-level pseudo-code, action SQL | Implementation reference |
| `docs/hld.md` | Goals, constraints, non-functional requirements, component responsibilities | Product/design context |
| `docs/database.md` | Full PostgreSQL schema — all tables, columns, types, constraints | DB questions |
| `MASTER.md` (this file) | Deep explanations of every technology choice, concept, design decision, and industry context | Interview prep, cross-questions, onboarding |

### `docs/internals.md` — diagram index

| Section | What the diagram shows |
|---|---|
| 1. Request Lifecycle | Full sequence: Browser → Next.js → FastAPI → LangGraph → Azure/Qdrant/PG |
| 2. Complete LangGraph Workflow | All 13 nodes with every conditional edge and label |
| 3. Intent Classification | 6 query types and their downstream routing paths |
| 4. Parallel Agent Dispatch | Fan-out to 4 agents with all tool names, fan-in to reflection |
| 5. Reflection Confidence Gate | Scoring formula, corroboration boosts, 3-condition re-query decision |
| 6. Memory Layer | Dual-write store and retrieve side by side with exact truncation values |
| 7. HITL Suspend/Resume | Full sequence with approve and decline branches |
| 8. Action Execution | All 5 action types mapped to exact SQL statements |
| 9. OpsState Field Map | Every field grouped by the node that writes it |
| 10. Response Types | The 5 `response_type` values and when each fires |
| 11. Startup Order | Docker Compose `depends_on` chain + backend `lifespan()` steps |
| 12. Langfuse Observability | Opt-in tracing flow from config to per-span capture |
