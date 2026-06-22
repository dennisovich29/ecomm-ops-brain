from __future__ import annotations

import logging
import os

from langfuse.langchain import CallbackHandler
from langchain_core.callbacks import BaseCallbackHandler

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _ensure_langfuse_env() -> None:
    """Set Langfuse env vars from settings if not already set."""
    s = get_settings()
    if s.langfuse_public_key and "LANGFUSE_PUBLIC_KEY" not in os.environ:
        os.environ["LANGFUSE_PUBLIC_KEY"] = s.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = s.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = s.langfuse_host.strip('"')


def _langfuse_configured() -> bool:
    return bool(get_settings().langfuse_public_key)


def get_callbacks(session_id: str, agent_name: str) -> list[BaseCallbackHandler]:
    """Return a Langfuse CallbackHandler for a sub-agent node."""
    if not _langfuse_configured():
        return []
    _ensure_langfuse_env()
    try:
        handler = CallbackHandler()
        logger.info("✓ Langfuse handler created for %s", agent_name)
        return [handler]
    except Exception as exc:
        logger.warning("Langfuse handler creation failed: %s", exc)
        return []


def get_root_handler(session_id: str, user_query: str) -> CallbackHandler | None:
    """Create a top-level CallbackHandler for a chat turn."""
    if not _langfuse_configured():
        return None
    _ensure_langfuse_env()
    try:
        handler = CallbackHandler()
        logger.info("✓ Langfuse root handler created for session %s", session_id)
        return handler
    except Exception as exc:
        logger.warning("Langfuse root handler creation failed: %s", exc)
        return None
