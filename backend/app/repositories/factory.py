from __future__ import annotations

from app.core.config import get_settings
from app.repositories.interfaces import (
    ISalesRepository,
    IInventoryRepository,
    IMarketingRepository,
    ISupportRepository,
)


def _use_postgres() -> bool:
    """v1 / 'mock'  → mock repos (no DB needed)
       v2 / 'postgres' → live PostgreSQL repos
    """
    backend = get_settings().repo_backend
    return backend in ("v2", "postgres")


def get_sales_repo() -> ISalesRepository:
    if _use_postgres():
        from app.repositories.postgres.sales import PostgresSalesRepository
        return PostgresSalesRepository()
    from app.repositories.mock.sales import MockSalesRepository
    return MockSalesRepository()


def get_inventory_repo() -> IInventoryRepository:
    if _use_postgres():
        from app.repositories.postgres.inventory import PostgresInventoryRepository
        return PostgresInventoryRepository()
    from app.repositories.mock.inventory import MockInventoryRepository
    return MockInventoryRepository()


def get_marketing_repo() -> IMarketingRepository:
    if _use_postgres():
        from app.repositories.postgres.marketing import PostgresMarketingRepository
        return PostgresMarketingRepository()
    from app.repositories.mock.marketing import MockMarketingRepository
    return MockMarketingRepository()


def get_support_repo() -> ISupportRepository:
    if _use_postgres():
        from app.repositories.postgres.support import PostgresSupportRepository
        return PostgresSupportRepository()
    from app.repositories.mock.support import MockSupportRepository
    return MockSupportRepository()
