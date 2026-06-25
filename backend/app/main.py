from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


class _SuppressHealthCheck(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_SuppressHealthCheck())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.actions import router as actions_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.incidents import router as incidents_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.checkpointer import close_checkpointer, init_checkpointer
from app.db.postgres import create_tables, dispose_engine, seed_data
from app.db.qdrant import close_qdrant, ensure_collection
from app.graph.workflow import init_compiled_graph

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()

    if s.langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = s.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = s.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = s.langfuse_host.strip('"')
        logger.info("Langfuse tracing enabled (host=%s)", s.langfuse_host)

    try:
        await create_tables()
        await seed_data()
    except Exception as exc:
        logger.warning("Postgres unavailable, skipping table creation: %s", exc)

    try:
        checkpointer = await init_checkpointer(s.postgres_url_plain)
        init_compiled_graph(checkpointer)
        logger.info("LangGraph compiled with PostgresSaver checkpointer")
    except Exception as exc:
        logger.warning("PostgresSaver unavailable, falling back to MemorySaver: %s", exc)
        from langgraph.checkpoint.memory import MemorySaver
        init_compiled_graph(MemorySaver())

    try:
        await ensure_collection()
    except Exception as exc:
        logger.warning("Qdrant unavailable, skipping collection setup: %s", exc)

    yield

    await dispose_engine()
    await close_qdrant()
    try:
        await close_checkpointer()
    except Exception:
        pass


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="AI E-commerce Operations Brain",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[s.frontend_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(chat_router, prefix="/chat", tags=["chat"])
    app.include_router(actions_router, prefix="/actions", tags=["actions"])
    app.include_router(incidents_router, prefix="/incidents", tags=["incidents"])

    return app


app = create_app()
