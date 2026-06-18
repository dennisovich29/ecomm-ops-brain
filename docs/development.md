# Development Guide

## Local Setup Flow

```mermaid
flowchart TD
    A([start]) --> B["cp .env.example .env\nfill in AZURE_OPENAI_API_KEY\nand AZURE_OPENAI_ENDPOINT"]
    B --> C{run mode?}

    C -- Docker --> D["docker compose build\ndocker compose up -d"]
    C -- Local --> E["docker compose up postgres redis qdrant -d\n(infra only)"]

    D --> F[all services up\nfrontend :3000\nbackend :8000]

    E --> G["cd backend\npip install -e .[dev]\nuvicorn app.main:app --reload"]
    G --> H["cd frontend\npnpm install\npnpm dev"]
    H --> F
```

## Test Pipeline

```mermaid
flowchart LR
    A([Unit tests]) --> B["pytest tests/unit/\nno LLM calls\nno network"]
    B --> B1[test_intent_router.py]
    B --> B2[test_mock_repos.py]
    B --> B3[test_reflection_agent.py]

    C([Eval tests]) --> D["pytest tests/eval/ -m eval\nreal Azure OpenAI calls\nDeepEval metrics"]
    D --> D1[test_cases.json\ntest_deepeval.py]
```

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.12 |
| Node.js | 20 |
| pnpm | 9 |
| Docker + Docker Compose | v24+ |
| Azure OpenAI | deployed `gpt-4o` and `text-embedding-3-small` |

---

## Environment Variables

Copy `.env.example` to `.env` in the project root and fill in the values.

```powershell
# PowerShell / Windows
copy .env.example .env
```

### Required

| Variable | Description |
|---|---|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI resource key |
| `AZURE_OPENAI_ENDPOINT` | e.g. `https://my-resource.openai.azure.com/` |

### Optional (with defaults)

| Variable | Default | Description |
|---|---|---|
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Chat model deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | Azure OpenAI API version |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-small` | Embedding model deployment name |
| `POSTGRES_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/ecomm_ops` | SQLAlchemy async URL |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `QDRANT_COLLECTION` | `incidents` | Qdrant collection name |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `REPO_BACKEND` | `v2` | `v1` (mock data, no DB) or `v2` (live Postgres) |
| `API_SECRET_KEY` | `change-me` | Bearer token for API auth (enforcement skipped when `change-me`) |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed CORS origin |

### Observability (all optional)

| Variable | Description |
|---|---|
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key |
| `LANGFUSE_HOST` | Default: `https://cloud.langfuse.com` |
| `LANGCHAIN_TRACING_V2` | `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | LangSmith API key |

---

## Running Locally (without Docker)

### Backend

```bash
# 1. Create and activate a virtual environment
cd backend
python -m venv .venv
.venv\Scripts\activate          # PowerShell / Windows

# 2. Install dependencies
pip install -e ".[dev]"
# or with uv:
uv pip install -e ".[dev]"

# 3. Start infrastructure (Postgres, Qdrant, Redis) via Docker Compose
docker compose up postgres redis qdrant -d

# 4. Run the backend with hot reload
uvicorn app.main:app --reload --port 8000
```

The backend starts in `REPO_BACKEND=v2` mode by default — Postgres is required.

To use mock data without a database, set `REPO_BACKEND=v1` in your `.env`.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Running with Docker Compose

### Start all services

```powershell
# Build images and start all services in detached mode
docker compose up --build -d

# Attach to logs after starting
docker compose logs -f
```

### Development mode (hot reload)

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

The dev override mounts `./backend/app` and `./frontend/src` as volumes so code changes reload without rebuilding.

### Service ports

| Service | Host port |
|---|---|
| Frontend (Next.js) | 3000 |
| Backend (FastAPI) | 8000 |
| PostgreSQL | 5432 |
| Qdrant HTTP | 6333 |
| Qdrant gRPC | 6334 |
| Redis | 6379 |

### Useful commands

```powershell
docker compose logs -f                            # tail all service logs
docker compose logs -f backend                    # tail backend only
docker compose exec backend bash                  # open shell in backend container
docker compose ps                                 # list running containers
docker compose down                               # stop all services
docker compose down -v                            # stop + remove volumes
```

---

## Repository Backend: Mock vs Postgres

The `REPO_BACKEND` env var controls which repository implementation is loaded.

| Value | Behaviour |
|---|---|
| `v1` (or `mock`) | In-memory data from `repositories/mock/`. No database needed. |
| `v2` (or `postgres`) | SQLAlchemy queries against PostgreSQL. Default. Auto-seeds tables on startup. |

Set in your `.env` file:
```
REPO_BACKEND=v2
```

Or pass directly to Docker Compose via the `environment` section of the `backend` service.

---

## Running Tests

### Unit tests (no LLM calls, no network)

```powershell
cd backend
python -m pytest tests/unit/ -v
```

Unit test files:
- `tests/unit/test_intent_router.py` — intent classification logic
- `tests/unit/test_mock_repos.py` — mock repository data correctness
- `tests/unit/test_reflection_agent.py` — reflection agent confidence scoring and re-query logic

### LLM evaluation tests (DeepEval — requires Azure OpenAI)

```powershell
cd backend
python -m pytest tests/eval/ -v -m eval --tb=short
```

Test cases are defined in `tests/eval/test_cases.json`. These make real API calls and are slow. They are excluded from the unit test run.

### Integration tests

`tests/integration/` is present but empty — a placeholder for future end-to-end tests.

---

## Code Quality

```bash
# Lint + format check (ruff)
cd backend
ruff check app/ tests/
ruff format --check app/ tests/

# Type checking (mypy)
mypy app/

# Auto-fix formatting
ruff format app/ tests/
```

Ruff is configured in `pyproject.toml`:
- `target-version = "py312"`
- `line-length = 100`

---

## Docker Compose Command Reference

| Goal | Command |
|---|---|
| Build images | `docker compose build` |
| Start all (detached) | `docker compose up -d` |
| Build + start | `docker compose up --build -d` |
| Start with hot reload | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` |
| Stop all | `docker compose down` |
| Tail all logs | `docker compose logs -f` |
| Tail backend logs | `docker compose logs -f backend` |
| Tail frontend logs | `docker compose logs -f frontend` |
| Stop + wipe volumes | `docker compose down -v` |
| Shell into backend | `docker compose exec backend bash` |
| Shell into frontend | `docker compose exec frontend sh` |
| `make ps` | List running containers |
| `make prune` | Full Docker system prune (destructive) |
| `make test` | Run unit tests |
| `make eval` | Run DeepEval LLM evaluation suite |
