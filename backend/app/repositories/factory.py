from __future__ import annotations

from app.repositories.interfaces import (
    ISalesRepository,
    IInventoryRepository,
    IMarketingRepository,
    ISupportRepository,
)


def get_sales_repo() -> ISalesRepository:
    from app.repositories.postgres.sales import PostgresSalesRepository
    return PostgresSalesRepository()


def get_inventory_repo() -> IInventoryRepository:
    from app.repositories.postgres.inventory import PostgresInventoryRepository
    return PostgresInventoryRepository()


def get_marketing_repo() -> IMarketingRepository:
    from app.repositories.postgres.marketing import PostgresMarketingRepository
    return PostgresMarketingRepository()


def get_support_repo() -> ISupportRepository:
    from app.repositories.postgres.support import PostgresSupportRepository
    return PostgresSupportRepository()
