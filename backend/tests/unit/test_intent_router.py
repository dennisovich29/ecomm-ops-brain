import pytest
from unittest.mock import AsyncMock, patch
from app.agents.intent_router import route_intent


@pytest.mark.asyncio
async def test_diagnostic_intent():
    mock_output = type("O", (), {
        "query_type": "DIAGNOSTIC",
        "domains": ["sales", "inventory"],
        "time_range": {"start": "2026-06-10", "end": "2026-06-10"},
        "entities": [],
    })()

    with patch("app.agents.intent_router.get_chat_llm") as mock_llm:
        llm = AsyncMock()
        llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.return_value = llm
        result = await route_intent("Why did sales drop yesterday?")

    assert result["query_type"] == "DIAGNOSTIC"
    assert "sales" in result["domains"]


@pytest.mark.asyncio
async def test_action_intent():
    mock_output = type("O", (), {
        "query_type": "ACTION",
        "domains": ["inventory"],
        "time_range": {"start": "2026-06-10", "end": "2026-06-10"},
        "entities": [],
    })()

    with patch("app.agents.intent_router.get_chat_llm") as mock_llm:
        llm = AsyncMock()
        llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.return_value = llm
        result = await route_intent("Fix the problem.")

    assert result["query_type"] == "ACTION"


@pytest.mark.asyncio
async def test_memory_intent():
    mock_output = type("O", (), {
        "query_type": "MEMORY",
        "domains": [],
        "time_range": {"start": "2026-06-10", "end": "2026-06-10"},
        "entities": [],
    })()

    with patch("app.agents.intent_router.get_chat_llm") as mock_llm:
        llm = AsyncMock()
        llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_output)
        mock_llm.return_value = llm
        result = await route_intent("What did we do last time this happened?")

    assert result["query_type"] == "MEMORY"
