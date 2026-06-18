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
    """Return a Langfuse CallbackHandler for a sub-agent node.

    When called inside a langfuse.start_as_current_observation() context (set up
    in the chat route), the handler automatically nests under the current trace
    via Python contextvars propagation.
    """
    if not _langfuse_configured():
        return []
    _ensure_langfuse_env()
    try:
        # CallbackHandler auto-configures from LANGFUSE_* env vars
        handler = CallbackHandler()
        logger.info(f"✓ Langfuse handler created for {agent_name}")
        return [handler]
    except Exception as exc:
        logger.warning("Langfuse handler creation failed: %s", exc)
        return []


def get_root_handler(session_id: str, user_query: str) -> CallbackHandler | None:
    """Create a top-level CallbackHandler for a chat turn.

    Pass this in the LangGraph invoke config so the full workflow is traced as
    one unit. Carries langfuse_session_id so all turns for a session are grouped
    in the Langfuse UI.
    """
    if not _langfuse_configured():
        return None
    _ensure_langfuse_env()
    try:
        # CallbackHandler auto-configures from LANGFUSE_* env vars
        handler = CallbackHandler()
        logger.info(f"✓ Langfuse root handler created for session {session_id}")
        return handler
    except Exception as exc:
        logger.warning("Langfuse root handler creation failed: %s", exc)
        return None
