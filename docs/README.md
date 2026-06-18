# AI E-commerce Operations Brain — Docs

| Doc | What's inside |
|---|---|
| [architecture.md](architecture.md) | Container diagram, component diagram, tech stack |
| [agent-design.md](agent-design.md) | LangGraph workflow, agent tools, reflection logic |
| [api-reference.md](api-reference.md) | Endpoint sequence diagrams |
| [data-model.md](data-model.md) | ER diagram, Pydantic class diagrams |
| [frontend.md](frontend.md) | Component tree, state diagram, SSE flow |
| [development.md](development.md) | Setup steps, test commands |
| [deployment.md](deployment.md) | Docker Compose service graph, startup sequence |

## System Context

```mermaid
C4Context
    title System Context — AI E-commerce Operations Brain

    Person(user, "Business User", "Asks operational questions via chat")

    System(brain, "Ecomm Ops Brain", "Multi-agent AI system: diagnoses issues, proposes and executes corrective actions")

    System_Ext(aoai, "Azure OpenAI", "GPT-4o + text-embedding-3-small")
    System_Ext(langfuse, "Langfuse / LangSmith", "LLM tracing & observability")

    Rel(user, brain, "Chat queries & HITL approvals", "HTTPS / SSE")
    Rel(brain, aoai, "LLM inference & embeddings", "HTTPS")
    Rel(brain, langfuse, "Traces & spans", "HTTPS")
```

## Container Diagram

```mermaid
C4Container
    title Containers — AI E-commerce Operations Brain

    Person(user, "Business User")

    Container(fe, "Next.js Frontend", "Next.js 15 / JavaScript", "Chat UI, approval panel, incident sidebar")
    Container(be, "FastAPI Backend", "Python 3.12 / FastAPI", "LangGraph orchestrator + REST/SSE API")
    ContainerDb(pg, "PostgreSQL 16", "Relational DB", "Incidents, sales, inventory, campaigns, tickets")
    ContainerDb(qd, "Qdrant", "Vector DB", "Incident embeddings for semantic retrieval")
    ContainerDb(rd, "Redis 7", "Cache", "Per-session working memory")

    Rel(user, fe, "Browser", "HTTPS")
    Rel(fe, be, "API proxy", "HTTP / SSE")
    Rel(be, pg, "SQLAlchemy asyncpg", "TCP 5432")
    Rel(be, qd, "qdrant-client", "HTTP 6333")
    Rel(be, rd, "redis-py async", "TCP 6379")
```
