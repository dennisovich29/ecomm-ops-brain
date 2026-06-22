"""Unit tests for app.core.observability."""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock


def test_langfuse_not_configured_returns_empty_callbacks():
    with patch("app.core.observability.get_settings") as mock_settings:
        mock_settings.return_value.langfuse_public_key = ""
        from app.core.observability import get_callbacks
        result = get_callbacks("session-1", "test_agent")
    assert result == []


def test_langfuse_not_configured_returns_none_root_handler():
    with patch("app.core.observability.get_settings") as mock_settings:
        mock_settings.return_value.langfuse_public_key = ""
        from app.core.observability import get_root_handler
        result = get_root_handler("session-1", "test query")
    assert result is None


def test_langfuse_configured_returns_handler():
    with patch("app.core.observability.get_settings") as mock_settings, \
         patch("app.core.observability.CallbackHandler") as mock_handler_cls:
        mock_settings.return_value.langfuse_public_key = "pk-lf-test"
        mock_settings.return_value.langfuse_secret_key = "sk-lf-test"
        mock_settings.return_value.langfuse_host = "https://cloud.langfuse.com"
        mock_handler_cls.return_value = MagicMock()
        from app.core.observability import get_callbacks
        result = get_callbacks("session-1", "test_agent")
    assert len(result) == 1


def test_langfuse_handler_creation_failure_returns_empty():
    with patch("app.core.observability.get_settings") as mock_settings, \
         patch("app.core.observability.CallbackHandler", side_effect=Exception("conn error")):
        mock_settings.return_value.langfuse_public_key = "pk-lf-test"
        mock_settings.return_value.langfuse_secret_key = "sk-lf-test"
        mock_settings.return_value.langfuse_host = "https://cloud.langfuse.com"
        from app.core.observability import get_callbacks
        result = get_callbacks("session-1", "test_agent")
    assert result == []


def test_langfuse_root_handler_configured():
    with patch("app.core.observability.get_settings") as mock_settings, \
         patch("app.core.observability.CallbackHandler") as mock_handler_cls:
        mock_settings.return_value.langfuse_public_key = "pk-lf-test"
        mock_settings.return_value.langfuse_secret_key = "sk-lf-test"
        mock_settings.return_value.langfuse_host = "https://cloud.langfuse.com"
        mock_handler_cls.return_value = MagicMock()
        from app.core.observability import get_root_handler
        result = get_root_handler("session-1", "why did sales drop?")
    assert result is not None
