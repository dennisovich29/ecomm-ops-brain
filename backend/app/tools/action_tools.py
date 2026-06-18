from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text

from app.db.postgres import get_db_session
from app.models.actions import ActionResult


async def execute_action(action: dict) -> dict:
    action_type = action.get("action_type", "unknown")
    params = action.get("parameters", {})
    action_id = action.get("action_id", "")

    handlers = {
        "restock_product": _restock_product,
        "apply_discount": _apply_discount,
        "pause_campaign": _pause_campaign,
        "resume_campaign": _resume_campaign,
        "create_support_ticket": _create_support_ticket,
    }

    handler = handlers.get(action_type)
    if handler:
        try:
            message = await handler(params)
            success = True
        except Exception as exc:
            message = f"Action failed: {exc}"
            success = False
    else:
        message = f"Unknown action type: {action_type}"
        success = False

    result = ActionResult(
        action_id=action_id,
        action_type=action_type,
        success=success,
        message=message,
        executed_at=datetime.now(timezone.utc).isoformat(),
    )
    return result.model_dump(mode="json")


async def _restock_product(params: dict) -> str:
    product_id = params.get("product_id", "UNKNOWN")
    quantity = int(params.get("quantity", 0))
    today = date.today()

    async with get_db_session() as db:
        # Upsert: add quantity to today's stock level
        await db.execute(
            text("""
                INSERT INTO inventory (product_id, date, stock_level, reorder_point)
                VALUES (:pid, :d, :qty, 50)
                ON CONFLICT (product_id, date)
                DO UPDATE SET stock_level = inventory.stock_level + :qty
            """),
            {"pid": product_id, "d": today, "qty": quantity},
        )
        await db.commit()

    return f"Restocked {product_id} +{quantity} units (effective today). Stock updated in DB."


async def _apply_discount(params: dict) -> str:
    product_id = params.get("product_id", "UNKNOWN")
    discount_pct = float(params.get("discount_pct", 10))
    promo_id = f"PROMO-{product_id}-{datetime.now(timezone.utc).strftime('%m%d%H%M')}"

    async with get_db_session() as db:
        await db.execute(
            text("""
                INSERT INTO promotions (id, name, discount_pct, products, status, scheduled_at)
                VALUES (:id, :name, :pct, :products, 'active', NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": promo_id,
                "name": f"Auto-discount {discount_pct}% on {product_id}",
                "pct": discount_pct,
                "products": [product_id],
            },
        )
        await db.commit()

    return f"Applied {discount_pct}% discount to {product_id} (promo ID: {promo_id}). Active immediately."


async def _pause_campaign(params: dict) -> str:
    campaign_id = params.get("campaign_id", "UNKNOWN")

    async with get_db_session() as db:
        result = await db.execute(
            text("UPDATE campaigns SET status = 'paused' WHERE id = :id"),
            {"id": campaign_id},
        )
        await db.commit()
        updated = result.rowcount

    if updated == 0:
        # Fetch available IDs so the caller knows what to use
        async with get_db_session() as db:
            rows = await db.execute(text("SELECT id FROM campaigns ORDER BY id"))
            ids = [r[0] for r in rows.fetchall()]
        return f"Campaign {campaign_id!r} not found. Available campaign IDs: {ids}. No change made."
    return f"Campaign {campaign_id} paused in DB."


async def _resume_campaign(params: dict) -> str:
    campaign_id = params.get("campaign_id", "UNKNOWN")

    async with get_db_session() as db:
        result = await db.execute(
            text("UPDATE campaigns SET status = 'active' WHERE id = :id"),
            {"id": campaign_id},
        )
        await db.commit()
        updated = result.rowcount

    if updated == 0:
        async with get_db_session() as db:
            rows = await db.execute(text("SELECT id FROM campaigns ORDER BY id"))
            ids = [r[0] for r in rows.fetchall()]
        return f"Campaign {campaign_id!r} not found. Available campaign IDs: {ids}. No change made."
    return f"Campaign {campaign_id} resumed (status → active) in DB."


async def _create_support_ticket(params: dict) -> str:
    issue_type = params.get("issue_type", "general")
    description = params.get("description", "")
    ticket_id = str(uuid.uuid4())

    async with get_db_session() as db:
        await db.execute(
            text("""
                INSERT INTO support_tickets (id, created_at, category, sentiment, resolved)
                VALUES (:id, NOW(), :category, 'neutral', false)
            """),
            {"id": ticket_id, "category": issue_type},
        )
        await db.commit()

    return f"Support ticket created (ID: {ticket_id[:8]}…) — category: {issue_type}."

