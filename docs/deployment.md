# Deployment

## Docker Compose Service Graph

```mermaid
graph TD
    subgraph Compose["docker-compose.yml"]
        PG[(postgres:16-alpine\n:5432)]
        QD[(qdrant:v1.9.2\n:6333 :6334)]
        RD[(redis:7-alpine\n:6379)]
        BE[backend\n:8000]
        FE[frontend\n:3000]
    end

    PG -- "healthy" --> BE
    RD -- "healthy" --> BE
    QD -- "started" --> BE
    BE --> FE
```

---

## Docker Build Pipelines

```mermaid
flowchart LR
    subgraph BackendBuild["Backend Dockerfile (multi-stage)"]
        B1["builder stage\npython:3.12-slim\nuv install deps → .venv"] --> B2["runtime stage\npython:3.12-slim\ncopy .venv + app/\n~200 MB image"]
    end

    subgraph FrontendBuild["Frontend Dockerfile (multi-stage)"]
        F1["deps stage\nnode:20-alpine\npnpm install"] --> F2["builder stage\nnext build (standalone)"]
        F2 --> F3["runner stage\nnode:20-alpine\nnode server.js\n~60 MB image"]
    end

    B2 -- "uvicorn app.main:app\n--host 0.0.0.0 --port 8000" --> BERUN([backend container])
    F3 -- "node server.js\nport 3000" --> FERUN([frontend container])
```

---

## Backend Startup Sequence

```mermaid
sequenceDiagram
    participant App as FastAPI lifespan
    participant PG as PostgreSQL
    participant QD as Qdrant
    participant LG as LangGraph

    App->>PG: create_tables() + seed_data()
    alt Postgres unavailable and REPO_BACKEND=v1
        PG-->>App: warn + skip
    end

    App->>LG: init_compiled_graph()
    LG->>PG: PostgresSaver checkpointer
    alt Postgres unavailable
        PG-->>LG: error
        LG->>LG: fallback to MemorySaver
    end

    App->>QD: ensure_collection()
    alt Qdrant unavailable
        QD-->>App: warn + skip
    end

    App-->>App: yield (app ready)

    Note over App: shutdown
    App->>App: flush Langfuse
    App->>PG: dispose engine
    App->>QD: close client
    App->>App: close Redis + checkpointer
```

---

## Service Dependencies & Healthchecks

```mermaid
flowchart LR
    PG["postgres\ncheck: pg_isready\ninterval 5s · retries 5"]
    RD["redis\ncheck: redis-cli ping\ninterval 5s · retries 5"]
    QD["qdrant\nno healthcheck\nstarted condition"]
    BE["backend\ncheck: GET /ready\n200=ready 503=degraded"]
    FE["frontend"]

    PG -- healthy --> BE
    RD -- healthy --> BE
    QD -- started --> BE
    BE --> FE
```

---

## Volume Persistence

```mermaid
graph LR
    pgdata["pgdata volume"] --> PG[("PostgreSQL\n/var/lib/postgresql/data")]
    qdrantdata["qdrantdata volume"] --> QD[("Qdrant\n/qdrant/storage")]
    note["Redis: no volume\nworking memory only\ndata loss on restart OK"] -.-> RD[(Redis)]
```

---

## Dev vs Production Mode

```mermaid
flowchart TD
    ENV{Mode?}

    ENV -- dev --> DO["docker-compose.dev.yml overlay\nvolume mounts:\n./backend/app → /app/app\n./frontend/src → /app/src\nhot reload enabled"]

    ENV -- prod --> PO["docker-compose.yml only\nbuilt images\nno volume source mounts\nAPI_SECRET_KEY required"]
```

Commands:

| Goal | Command |
|---|---|
| Dev (hot reload) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` |
| Prod (detached) | `docker compose up --build -d` |
| Stop | `docker compose down` |
| Wipe volumes | `docker compose down -v` |

