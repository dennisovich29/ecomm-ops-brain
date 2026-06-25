from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.graph.workflow import get_compiled_graph


def verify_token(authorization: str | None = Header(default=None)) -> None:
    s = get_settings()
    if not s.api_secret_key or s.api_secret_key == "change-me":
        return
    if authorization != f"Bearer {s.api_secret_key}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token",
        )


def get_graph():
    return get_compiled_graph()

