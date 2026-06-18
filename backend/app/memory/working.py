from __future__ import annotations

import json
from typing import Any

from app.db.redis import get_redis_client

_TTL_SECONDS = 86400  # 24 hours


async def save_session_context(session_id: str, context: dict[str, Any]) -> None:
    client = get_redis_client()
    await client.setex(
        f"session:{session_id}",
        _TTL_SECONDS,
        json.dumps(context, default=str),
    )


async def get_session_context(session_id: str) -> dict | None:
    client = get_redis_client()
    raw = await client.get(f"session:{session_id}")
    if raw:
        return json.loads(raw)
    return None


async def clear_session(session_id: str) -> None:
    client = get_redis_client()
    await client.delete(f"session:{session_id}")


async def publish_event(channel: str, event: dict) -> None:
    """Publish a WebSocket-destined event via Redis pub/sub."""
    client = get_redis_client()
    await client.publish(channel, json.dumps(event, default=str))
