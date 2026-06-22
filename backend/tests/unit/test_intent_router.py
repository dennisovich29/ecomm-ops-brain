import pytest
from unittest.mock import MagicMock, patch
from langchain_core.runnables import RunnableLambda
from app.agents.intent_router import route_intent


def _make_mock_output(query_type, domains=None, time_range=None, entities=None):
    """Return a fake IntentOutput-like object."""
    from app.graph.state import TimeRange
    class FakeOutput:
        pass
    o = FakeOutput()
    o.query_type = query_type
    o.domains = domains or []
    o.time_range = TimeRange(start="2026-06-18", end="2026-06-18")
    o.entities = entities or []
    return o


def _mock_llm(output):
    """Return a MagicMock LLM whose with_structured_output returns a RunnableLambda."""
    structured_runnable = RunnableLambda(lambda _: output)
    llm = MagicMock()
    llm.with_structured_output.return_value = structured_runnable
    return llm


@pytest.mark.asyncio
async def test_diagnostic_intent():
    output = _make_mock_output("DIAGNOSTIC", ["sales", "inventory"])
    with patch("app.agents.intent_router.get_chat_llm", return_value=_mock_llm(output)), \
         patch("app.agents.intent_router.get_callbacks", return_value=[]):
        result = await route_intent("Why did sales drop yesterday?")
    assert result["query_type"] == "DIAGNOSTIC"
    assert "sales" in result["domains"]


@pytest.mark.asyncio
async def test_action_intent():
    output = _make_mock_output("ACTION", ["inventory"])
    with patch("app.agents.intent_router.get_chat_llm", return_value=_mock_llm(output)), \
         patch("app.agents.intent_router.get_callbacks", return_value=[]):
        result = await route_intent("Fix the problem.")
    assert result["query_type"] == "ACTION"


@pytest.mark.asyncio
async def test_memory_intent():
    output = _make_mock_output("MEMORY", [])
    with patch("app.agents.intent_router.get_chat_llm", return_value=_mock_llm(output)), \
         patch("app.agents.intent_router.get_callbacks", return_value=[]):
        result = await route_intent("What did we do last time this happened?")
    assert result["query_type"] == "MEMORY"


@pytest.mark.asyncio
async def test_general_intent():
    output = _make_mock_output("GENERAL", [])
    with patch("app.agents.intent_router.get_chat_llm", return_value=_mock_llm(output)), \
         patch("app.agents.intent_router.get_callbacks", return_value=[]):
        result = await route_intent("Hello!")
    assert result["query_type"] == "GENERAL"
    assert result["domains"] == []


@pytest.mark.asyncio
async def test_hybrid_intent():
    output = _make_mock_output("HYBRID", ["sales", "inventory", "marketing", "support"])
    with patch("app.agents.intent_router.get_chat_llm", return_value=_mock_llm(output)), \
         patch("app.agents.intent_router.get_callbacks", return_value=[]):
        result = await route_intent("Diagnose and fix everything.")
    assert result["query_type"] == "HYBRID"
    assert len(result["domains"]) == 4

