from __future__ import annotations

from datetime import date, timedelta

from langchain.tools import tool

from app.repositories.factory import get_support_repo


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


@tool
async def get_ticket_volume(target_date: str | None = None) -> dict:
    """Get total support ticket volume for a date and compare to 7-day average."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_support_repo()
    result = await repo.get_ticket_volume(d)
    return result.model_dump(mode="json")


@tool
async def get_refund_rates(target_date: str | None = None) -> dict:
    """Get refund and return rates for a date vs baseline."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_support_repo()
    result = await repo.get_refund_rates(d)
    return result.model_dump(mode="json")


@tool
async def get_complaint_themes(target_date: str | None = None) -> list[dict]:
    """Get top complaint themes from support tickets for a date."""
    d = date.fromisoformat(target_date) if target_date else _yesterday()
    repo = get_support_repo()
    results = await repo.get_complaint_themes(d)
    return [r.model_dump(mode="json") for r in results]


SUPPORT_TOOLS = [
    get_ticket_volume,
    get_refund_rates,
    get_complaint_themes,
]
