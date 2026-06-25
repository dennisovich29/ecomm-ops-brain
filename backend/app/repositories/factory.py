from __future__ import annotations

from app.repositories.interfaces import (
    ISalesRepository,
    IInventoryRepository,
    IMarketingRepository,
    ISupportRepository,
)
from app.repositories.inventory import PostgresInventoryRepository
from app.repositories.marketing import PostgresMarketingRepository
from app.repositories.sales import PostgresSalesRepository
from app.repositories.support import PostgresSupportRepository


def get_sales_repo() -> ISalesRepository:
    return PostgresSalesRepository()


def get_inventory_repo() -> IInventoryRepository:
    return PostgresInventoryRepository()


def get_marketing_repo() -> IMarketingRepository:
    return PostgresMarketingRepository()


def get_support_repo() -> ISupportRepository:
    return PostgresSupportRepository()
