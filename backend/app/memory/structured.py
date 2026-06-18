from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.postgres import get_db_session


async def get_incident_list(limit: int = 20) -> list[dict]:
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT id, created_at, query, root_cause, domains, confidence, resolved
                FROM incidents
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.mappings().all()
        return [dict(r) for r in rows]


async def get_incident_by_id(incident_id: str) -> dict | None:
    async with get_db_session() as session:
        result = await session.execute(
            text("SELECT * FROM incidents WHERE id = :id"),
            {"id": incident_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        incident = dict(row)

        actions_result = await session.execute(
            text("SELECT * FROM incident_actions WHERE incident_id = :id ORDER BY executed_at"),
            {"id": incident_id},
        )
        incident["actions"] = [dict(r) for r in actions_result.mappings().all()]
        return incident


async def store_action_outcome(
    incident_id: str,
    action_type: str,
    parameters: dict,
    approved: bool,
    outcome: str,
) -> None:
    async with get_db_session() as session:
        await session.execute(
            text("""
                INSERT INTO incident_actions
                    (incident_id, action_type, parameters, approved, executed_at, outcome)
                VALUES (:incident_id, :action_type, :parameters, :approved, :executed_at, :outcome)
            """),
            {
                "incident_id": incident_id,
                "action_type": action_type,
                "parameters": json.dumps(parameters),
                "approved": approved,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "outcome": outcome,
            },
        )
        await session.commit()
