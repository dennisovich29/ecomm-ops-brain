# Architecture — Ecomm Ops Brain

## System Context

```mermaid
graph TD
    Operator["Operator (Browser)"]
    FE["Next.js 15\nport 3000"]
    BE["FastAPI\nport 8000"]
    PG[("PostgreSQL 16\nport 5432")]
    QD[("Qdrant v1.9.2\nport 6333")]
    AZ["Azure OpenAI\nGPT-4o · text-embedding-3-small-1"]

    Operator -->|"chat / approve actions"| FE
    FE -->|"POST /api/chat/stream  SSE"| BE
    FE -->|"POST /api/actions/approve|decline"| BE
    BE -->|"LangGraph astream"| BE
    BE -->|"SQL — ops data + checkpoint state"| PG
    BE -->|"vector upsert / search"| QD
    BE -->|"LLM inference + embeddings"| AZ
```

All browser traffic routes through the Next.js proxy at `/api/*`. The browser never contacts the FastAPI backend directly.

---

## Component Diagram

```mermaid
graph TD
    subgraph Frontend["Next.js :3000"]
        UI["Chat UI\nSSE token stream"]
        HITL_UI["Inline Approval Card\nHITL"]
        SB["Incident Sidebar"]
    end

    subgraph API["FastAPI :8000"]
        CHAT["POST /chat/stream\nSSE"]
        APR["POST /actions/approve\nPOST /actions/decline"]
        INC["GET /incidents"]
        HEALTH["GET /health  GET /ready"]
    end

    subgraph Graph["LangGraph Workflow"]
        RI["route_intent\nIntent Router (GPT-4o)"]
        subgraph PAR["Parallel Dispatch"]
            SA["Sales Agent"]
            IA["Inventory Agent"]
            MA["Marketing Agent"]
            SUA["Support Agent"]
        end
        RF["run_reflection\nPure Python — confidence gate"]
        MEM["retrieve_memory\nQdrant similarity search"]
        SY["synthesize_findings\nGPT-4o RCA"]
        SI["store_incident\nQdrant + Postgres"]
        PA["propose_actions\nGPT-4o action generation"]
        HC["hitl_checkpoint\nLangGraph interrupt()"]
        EA["execute_actions\nSQL writes"]
        FR["format_response"]
    end

    subgraph Repos["Repository Layer"]
        RS["ISalesRepository"]
        RI2["IInventoryRepository"]
        RM["IMarketingRepository"]
        RSU["ISupportRepository"]
        PGR["PostgresImpl (v2 only)"]
    end

    UI -->|SSE| CHAT
    HITL_UI -->|REST| APR
    SB -->|REST| INC

    CHAT --> RI
    APR --> HC

    RI -->|"GENERAL / no domains"| FR
    RI -->|"has domains"| PAR
    PAR --> RF
    RF -->|"gaps + confidence < 0.70 + passes < 3"| RI
    RF -->|"SUMMARY"| FR
    RF -->|"else"| MEM
    MEM --> SY
    SY --> SI
    SI -->|"ACTION/HYBRID + action_requested"| PA
    SI -->|"else"| FR
    PA --> HC
    HC -->|"approved"| EA
    HC -->|"declined"| FR
    EA --> FR

    SA --> RS --> PGR
    IA --> RI2 --> PGR
    MA --> RM --> PGR
    SUA --> RSU --> PGR
```

---

## Docker Compose Services

```mermaid
graph LR
    FE["frontend\nNext.js :3000"]
    BE["backend\nFastAPI :8000"]
    PG["postgres\nPostgreSQL :5432"]
    QD["qdrant\nQdrant :6333"]

    FE -->|"depends_on: healthy"| BE
    BE -->|"depends_on: healthy"| PG
    BE -->|"depends_on: started"| QD
```

Startup is enforced via `depends_on` health conditions. Migrations run automatically from `backend/app/db/migrations/` at backend startup.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 App Router, Tailwind CSS, Zustand, SSE |
| Backend API | FastAPI 0.115, Python 3.12 |
| Orchestration | LangGraph 0.2, AsyncPostgresSaver checkpointer |
| LLM / Embeddings | Azure OpenAI GPT-4o, text-embedding-3-small-1 (1536-dim) |
| Agent Framework | LangChain 1.0, create_agent (v1 API) |
| Vector Store | Qdrant v1.9.2 — cosine similarity, score_threshold=0.5 |
| Relational DB | PostgreSQL 16, SQLAlchemy asyncio, asyncpg |
| Observability | Langfuse (LangChain callbacks) |
| Evaluation | DeepEval |
