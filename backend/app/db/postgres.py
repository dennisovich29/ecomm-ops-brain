from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

# Import all models so Base.metadata is populated before create_all runs
import app.db.models  # noqa: F401
from app.db.models import Base

_log = logging.getLogger(__name__)

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_async_engine(s.postgres_url, echo=False, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session


async def create_tables() -> None:
    """Create all tables via ORM metadata (idempotent — CREATE TABLE IF NOT EXISTS)."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _log.info("Database tables ready.")


async def seed_data() -> None:
    from app.db.seed import seed_data as _seed
    await _seed()


async def dispose_engine() -> None:
    engine = get_engine()
    await engine.dispose()
