# Ecomm Ops Brain — Interview Guide

Read this top to bottom. Each section is a talking point. The flow builds on itself — each section assumes the interviewer has heard the one before.

---

## The Problem I Was Solving

E-commerce operations teams spend a lot of time manually checking dashboards — revenue dropped, why? Is it a stockout? A paused campaign? A refund spike? The answer usually lives across four different data sources and takes 20–30 minutes to piece together manually.

I built a system that takes a natural language question like *"Why did sales drop yesterday?"* and automatically investigates across all four domains — sales, inventory, marketing, and support — in parallel, synthesises a root cause analysis, and if needed, proposes corrective actions and executes them after human approval. The whole thing runs in under 15 seconds.

---

## The High-Level Architecture

The system has three layers. The frontend is **Next.js 15**, which proxies all requests through its own `/api` routes to the FastAPI backend — the browser never talks to the backend directly, which keeps auth simple and eliminates CORS issues entirely.

The backend is **FastAPI** running async Python 3.12. Every request hits a single POST endpoint that streams a response back using **Server-Sent Events** — so the user sees tokens appearing in real time as GPT-4o generates them.

The orchestration layer is **LangGraph** — a stateful graph of 13 nodes. That's where all the intelligence lives.

The external services are **Azure OpenAI** for GPT-4o and embeddings, **PostgreSQL 16** for operational data and graph state persistence, and **Qdrant** as the vector store for episodic memory.

---

## Walking Through a Query — The Full Flow

When a user sends a message, here's exactly what happens:

**Step 1 — Intent Classification.** The first node, `route_intent`, makes a single GPT-4o call using `with_structured_output` — which forces the model to return a validated Pydantic object rather than free text. It produces five fields: query type (one of DIAGNOSTIC, ACTION, MEMORY, SUMMARY, HYBRID, or GENERAL), the relevant domains, a time range, named entities mentioned, and a boolean for whether the user explicitly asked for an action to be taken. That last field is important and I'll come back to it.

**Step 2 — Parallel Agent Dispatch.** LangGraph's conditional edge returns a *list* of node names, which LangGraph executes concurrently. So if the query involves sales and inventory, both agents run at the same time. Each agent is a LangChain ReAct-style agent created with `create_agent`, equipped with domain-specific SQL tools. The sales agent has tools like `get_daily_revenue`, `detect_sales_anomaly`, `compare_sales_periods`. The inventory agent has `get_stock_levels`, `get_stockout_events`, and so on. Without parallelism, four agents at roughly 3 seconds each would be 12 seconds. With it, it's 3 seconds total.

**Step 3 — Reflection.** After all agents complete, the `run_reflection` node runs. This is the only node in the entire graph with zero LLM calls — it's pure Python. It scores confidence by checking how many requested domains returned findings, then adds corroboration boosts — for example if inventory shows stockout events AND sales shows a revenue drop, that's more credible than either alone, so confidence gets a +0.10 boost. The threshold is 0.70. If confidence is below that AND there are gaps AND we haven't exceeded 3 passes, it loops back to `route_intent` and re-dispatches only the agents for the missing domains, preserving the findings we already have.

**Step 4 — Memory Retrieval.** Once reflection passes, before synthesising anything, the system searches for similar past incidents. It builds a rich text representation of the current state — the user query, root cause fragments, all domain findings — embeds it with `text-embedding-3-small-1` (1536 dimensions), and does a cosine similarity search in Qdrant with a score threshold of 0.5. The top 3 similar incidents come back with their root causes and what actions were taken at the time.

**Step 5 — Synthesis.** GPT-4o now has everything: all domain findings plus historical context from similar incidents plus the last few turns of conversation history. It produces the root cause analysis narrative. This is the only node that streams tokens to the frontend — all other LLM calls run silently because showing the JSON intent classification or raw tool results in the chat would be confusing.

**Step 6 — Store Incident.** Every completed analysis is immediately stored — embedded into Qdrant and mirrored to Postgres. This is unconditional, regardless of whether actions follow, because if storage only happened after action execution, pure diagnostic queries would never build up the episodic memory at all.

**Step 7 — Actions (if applicable).** If the query type is ACTION or the user explicitly asked for an action on a HYBRID query, the system proposes corrective actions. Before calling GPT-4o here, it fetches all valid product IDs and campaign IDs from Postgres and injects them into the system prompt. This grounds the LLM — it can only propose actions on entities that actually exist in the database. Without this, you'd get hallucinated product IDs.

**Step 8 — HITL.** The proposed actions hit a `hitl_checkpoint` node which calls LangGraph's `interrupt()`. This serialises the entire graph state to PostgreSQL using `AsyncPostgresSaver` and stops execution completely. The frontend renders an approval card. The operator reviews each action with its justification and impact estimate. If they approve, the frontend posts to `/actions/approve`, the graph is resumed from the checkpoint, and the approved actions are executed as SQL writes. If they decline, the graph formats a normal response without executing anything.

---

## Why LangGraph — The Most Important Choice

I chose LangGraph specifically because I needed three things that a standard LangChain LCEL pipeline can't do.

First, **stateful cycles** — the reflection loop where the graph can loop back to `route_intent` up to three times. A linear chain has no concept of cycles.

Second, **true parallelism** — the fan-out to multiple agents with a fan-in at reflection. LCEL doesn't natively express "run all of these concurrently and wait for all of them."

Third, and most important — **interrupt and resume for HITL**. LangGraph's `interrupt()` pauses the graph mid-execution and stores the full state in PostgreSQL. The graph can be resumed hours later, even after a server restart, because the state is in the database not in memory. A `MemorySaver` would lose the state on any restart. `AsyncPostgresSaver` persists it durably. This is what makes the HITL approval window reliable — it's not a thread sleeping, it's a completely suspended execution with durable state.

---

## The HITL Design — Why It Matters

The reason HITL exists is simple: AI systems can be confidently wrong. In e-commerce, executing the wrong action — pausing a healthy campaign, applying a discount to the wrong product — has real business impact. So the system investigates and proposes, but humans decide.

The flow technically: `hitl_checkpoint` calls `interrupt(proposed_actions)`. LangGraph writes the full `OpsState` to the `checkpoint_blobs` table in Postgres and raises an internal exception that terminates the `astream()` call. The API detects the pause by checking `graph.aget_state(config).next` — if that tuple is non-empty, the graph is suspended. It sends an `approval_pending` SSE event.

When the operator approves, the frontend posts the approved action IDs. FastAPI calls `graph.aupdate_state()` to inject the approved IDs, then `graph.astream(None, config)` to resume. LangGraph loads the state from Postgres, the `interrupt()` call returns the approved IDs, and execution continues into `execute_actions`. From the graph's perspective, it never stopped.

---

## The Reflection Loop — Why Pure Python

A common question is why reflection has no LLM. The answer is that confidence scoring is a deterministic check — did the inventory agent return data? Yes or no. If yes, did it return specifically `stockout_events`? These are field presence checks, not reasoning tasks. Using an LLM here would add latency and introduce variability to what is fundamentally a data presence assertion. Pure Python is predictable, fast, and fully unit-testable.

The re-query is bounded by `MAX_REFLECTION_PASSES = 3` and requires all three conditions simultaneously: gaps must exist, passes must be under 3, and confidence must be below 0.70. If any one condition is false — maybe confidence is high despite one missing domain — it proceeds to synthesis rather than looping forever.

---

## Episodic Memory — Why It's Designed This Way

The same `_build_incident_text()` function builds the text representation for both storage and retrieval. This is intentional — it ensures the query vector is in the same semantic space as the stored vectors. If storage builds a rich text and retrieval uses a sparse text, the cosine similarity breaks down.

The system dual-writes to Qdrant (the semantic search engine) and Postgres (for structured queries and the incident sidebar in the frontend). The Postgres write is best-effort — if it fails, a warning is logged but the Qdrant write already succeeded, so memory retrieval still works. Qdrant is the source of truth for semantic memory.

The truncation limits — 400 characters for root cause, 200 per domain findings — are deliberate. They keep the embedding input under token limits while preserving the most semantically dense content.

---

## Agent Middleware — A Detail Worth Mentioning

Each specialist agent has a middleware stack passed via `middleware=[]` to `create_agent`. This is a LangChain v1 feature that runs cross-cutting concerns around every LLM call without touching agent logic.

All four agents get `SummarizationMiddleware` — if the agent's conversation history hits 2,000 tokens during a multi-tool investigation, it summarises older messages in place and keeps the last 20. This prevents long investigations from overflowing the context window. They also get `resilient_tool_call`, a custom `@wrap_tool_call` middleware that catches any tool exception and returns a graceful error message instead of crashing — so if a DB query fails, the agent gets the error text, adapts, and continues with partial data.

The support agent gets two extra layers: `PIIMiddleware("email")` and `PIIMiddleware("phone_number")` — these redact customer contact details from ticket text before it reaches the LLM. Phone numbers are a custom type requiring a regex detector since they're not a LangChain built-in. This is applied only to the support agent because that's the only domain that processes real customer data.

---

## Technology Choices — The Quick Version

**FastAPI** over Flask or Django because it's async-first — every request involves multiple LLM calls that take seconds, and async lets one thread handle many concurrent requests instead of blocking.

**Azure OpenAI** over OpenAI direct because data stays in our Azure tenant — no data residency concerns, enterprise SLAs, compliance.

**Qdrant** over pgvector because Qdrant is purpose-built for vector search with HNSW indexing and async client support. pgvector is slower for pure similarity search at scale.

**Zustand** on the frontend because it has minimal boilerplate and session-keyed state without the Provider hell of React Context or the weight of Redux.

**pydantic-settings** for configuration with `@lru_cache` on `get_settings()` — settings are parsed from environment variables exactly once at startup, not on every request.

---

## The Interesting Problem I Solved

The most interesting design problem was the `store_incident` placement. Originally, incident storage only ran after `execute_actions` — meaning if a user asked a diagnostic question and no actions were taken, the incident never got stored. The episodic memory stayed empty no matter how many queries ran.

The fix was to make `store_incident` run unconditionally after `synthesize_findings`, before the action branch decision. The routing to `propose_actions` vs `format_response` is a separate decision made by `edge_after_synthesis` based on `action_requested`. Storage and action proposal are now fully independent. This required thinking carefully about graph topology — which edges are conditional vs fixed, and what the actual dependency relationship is between nodes.

---

## Numbers to Remember

| Thing | Value |
|---|---|
| LangGraph nodes | 13 |
| Confidence threshold | 0.70 |
| Max reflection passes | 3 |
| Embedding dimensions | 1536 |
| Qdrant score threshold | 0.5 |
| Similar incidents retrieved | top 3 |
| Root cause truncation | 400 chars |
| Domain findings truncation | 200 chars per domain |
| Summarisation trigger | 2,000 tokens |
| Summarisation keep | last 20 messages |
| Parallel speedup | ~12s → ~3s (4 agents) |
| LangGraph overhead | ~4ms (vs LCEL ~10ms) |
| PostgreSQL tables | 11 ops + 2 incident + 3 checkpoint |
| Query types | 6 (DIAGNOSTIC, ACTION, MEMORY, SUMMARY, HYBRID, GENERAL) |
| Action types | 5 (restock, discount, pause, resume, support ticket) |
