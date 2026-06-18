from __future__ import annotations

from datetime import date, timedelta

from langchain.tools import tool

from app.repositories.factory import get_marketing_repo


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


@tool
async def get_campaign_metrics(target_date: str | None = None) -> list[dict]:
    """Get performance metrics for all campaigns on a given date. Defaults to yesterday."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_marketing_repo()
    results = await repo.get_campaign_metrics(d)
    return [r.model_dump(mode="json") for r in results]


@tool
async def get_channel_performance(target_date: str | None = None) -> list[dict]:
    """Get revenue and ROAS broken down by marketing channel for a given date."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_marketing_repo()
    results = await repo.get_channel_performance(d)
    return [r.model_dump(mode="json") for r in results]


@tool
async def get_active_promotions() -> list[dict]:
    """Get all currently active, scheduled, or recently missed promotions."""
    repo = get_marketing_repo()
    results = await repo.get_active_promotions()
    return [r.model_dump(mode="json") for r in results]


MARKETING_TOOLS = [
    get_campaign_metrics,
    get_channel_performance,
    get_active_promotions,
]
