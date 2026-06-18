from __future__ import annotations

import pathlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_MIGRATION_SQL = (
    pathlib.Path(__file__).parent / "migrations" / "001_initial_schema.sql"
)


def _make_engine():
    s = get_settings()
    return create_async_engine(s.postgres_url, echo=False, pool_pre_ping=True)


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def _parse_sql_file(path: pathlib.Path) -> list[str]:
    statements = []
    for raw in path.read_text().split(";"):
        lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements


async def create_tables() -> None:
    migrations = [
        pathlib.Path(__file__).parent / "migrations" / "001_initial_schema.sql",
        pathlib.Path(__file__).parent / "migrations" / "003_extend_schema.sql",
    ]
    async with get_engine().begin() as conn:
        for path in migrations:
            for stmt in _parse_sql_file(path):
                await conn.execute(text(stmt))


async def seed_data() -> None:
    seed_migrations = [
        pathlib.Path(__file__).parent / "migrations" / "002_seed_data.sql",
        pathlib.Path(__file__).parent / "migrations" / "004_varied_seed_data.sql",
    ]
    async with get_engine().begin() as conn:
        for path in seed_migrations:
            if path.exists():
                for stmt in _parse_sql_file(path):
                    await conn.execute(text(stmt))


async def dispose_engine() -> None:
    engine = get_engine()
    await engine.dispose()
