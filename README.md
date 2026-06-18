# AI E-commerce Operations Brain

Multi-agent AI system that operates as a smart operations manager for an e-commerce business.

## Quick Start

```bash
# 1. Copy environment variables
copy .env.example .env
# Edit .env — fill in AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT at minimum

# 2. Start all services
docker compose up --build -d

# 3. Open http://localhost:3000
```

For local (non-Docker) development see [docs/development.md](docs/development.md).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design.

## Implementation Plan

See [PLAN.md](PLAN.md) for the phased implementation roadmap.

## Demo Scenarios

**1. Diagnostic — "Why did sales drop yesterday?"**
- Dispatches Sales, Inventory, Marketing, Support agents in parallel
- Reflection agent scores confidence (0.88)
- Returns root cause: top-3 SKUs out of stock + paid search campaign paused

**2. Action — "Fix the problem."**
- Action agent proposes: restock SKU-001, SKU-002, resume campaign
- HITL approval modal appears in frontend
- LangGraph interrupt() pauses graph, waits for human decision
- Approved actions execute and log to Postgres

**3. Memory — "What did we do last time this happened?"**
- Embeds current incident → Qdrant semantic search
- Returns 2–3 similar past incidents with actions taken and outcomes

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness check |
| GET | /ready | Readiness check (all services) |
| POST | /chat | Synchronous query |
| POST | /chat/stream | SSE streaming response |
| POST | /actions/approve | Resume graph — approve selected actions |
| POST | /actions/decline | Resume graph — decline all actions |
| GET | /incidents | List incident history |
| GET | /incidents/{id} | Get single incident |

## Environment Variables

See `.env.example` for all required variables.

Minimum required:
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT` (default: `gpt-4o`)
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` (default: `text-embedding-3-small`)
- `REPO_BACKEND` — `v1` (mock data, no DB) or `v2` (live Postgres, default)

## Running Tests

```bash
# Unit tests (no LLM calls)
cd backend
python -m pytest tests/unit/ -v

# DeepEval agent evaluation (requires Azure OpenAI)
python -m pytest tests/eval/ -v -m eval --tb=short
```

## Project Structure

```
ecomm-ops-brain/
├── backend/app/
│   ├── agents/          # Intent router, specialist agents, reflection, action
│   ├── graph/           # LangGraph state, nodes, edges, workflow
│   ├── tools/           # LangChain tools for each domain + action executors
│   ├── repositories/    # Mock (v1) + Postgres (v2) implementations
│   ├── memory/          # Episodic (Qdrant), working (Redis), structured (Postgres)
│   ├── api/routes/      # FastAPI endpoints (chat, actions, incidents, health)
│   └── core/            # Config, LLM factory, observability
└── frontend/src/
    ├── app/             # Next.js App Router pages + API proxy routes
    ├── components/      # MessageBubble, Sidebar, InputBar, ApprovalPanel, etc.
    ├── hooks/           # useChat (SSE streaming + store updates)
    └── lib/             # Zustand store (store.js) + API client (api.js)
```
