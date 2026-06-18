from __future__ import annotations

from langchain.tools import tool
from datetime import date, timedelta

from app.repositories.factory import get_sales_repo


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


@tool
async def get_daily_revenue(target_date: str | None = None) -> dict:
    """Get revenue, order count, and AOV for a specific date (YYYY-MM-DD). Defaults to yesterday."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_sales_repo()
    result = await repo.get_daily_revenue(d)
    return result.model_dump(mode="json")


@tool
async def get_product_sales_breakdown(target_date: str | None = None) -> list[dict]:
    """Get per-product revenue and units sold breakdown for a date. Defaults to yesterday."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_sales_repo()
    results = await repo.get_product_breakdown(d)
    return [r.model_dump(mode="json") for r in results]


@tool
async def get_regional_sales(target_date: str | None = None) -> list[dict]:
    """Get sales broken down by region for a date. Defaults to yesterday."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_sales_repo()
    results = await repo.get_regional_breakdown(d)
    return [r.model_dump(mode="json") for r in results]


@tool
async def detect_sales_anomaly(target_date: str | None = None) -> dict:
    """Detect whether sales on a given date are a statistical anomaly vs the 30-day baseline."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_sales_repo()
    result = await repo.detect_anomaly(d)
    return result.model_dump(mode="json")


@tool
async def compare_sales_periods(target_date: str | None = None) -> dict:
    """Compare sales for a date against prior day and prior week same day."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_sales_repo()
    return await repo.compare_periods(d)


SALES_TOOLS = [
    get_daily_revenue,
    get_product_sales_breakdown,
    get_regional_sales,
    detect_sales_anomaly,
    compare_sales_periods,
]
