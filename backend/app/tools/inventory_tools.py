from __future__ import annotations

from datetime import date, timedelta

from langchain.tools import tool

from app.repositories.factory import get_inventory_repo


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


@tool
async def get_stock_levels(product_ids: list[str] | None = None) -> list[dict]:
    """Get current stock levels for all products, or a specific list of product IDs."""
    repo = get_inventory_repo()
    results = await repo.get_stock_levels(product_ids)
    return [r.model_dump(mode="json") for r in results]


@tool
async def get_stockout_events(target_date: str | None = None) -> list[dict]:
    """Get products that went out of stock on a given date. Defaults to yesterday."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_inventory_repo()
    results = await repo.get_stockout_events(d)
    return [r.model_dump(mode="json") for r in results]


@tool
async def get_restock_recommendations() -> list[dict]:
    """Get recommended restock quantities and urgency for low/out-of-stock products."""
    repo = get_inventory_repo()
    results = await repo.get_restock_recommendations()
    return [r.model_dump(mode="json") for r in results]


@tool
async def get_views_vs_purchases(target_date: str | None = None) -> list[dict]:
    """Get products that were viewed but not purchased, indicating lost conversions from stockouts."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_inventory_repo()
    return await repo.get_views_vs_purchases(d)


INVENTORY_TOOLS = [
    get_stock_levels,
    get_stockout_events,
    get_restock_recommendations,
    get_views_vs_purchases,
]
