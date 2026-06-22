"""Tests for action_agent, episodic/structured memory, workflow, chat route, specialist nodes."""
from __future__ import annotations

import json
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.graph.state import OpsState


def _base_state(**overrides) -> OpsState:
    base: OpsState = {
        "user_query": "Why did sales drop yesterday?",
        "session_id": "sess-test",
        "turn_id": "turn-test",
        "intent": {"query_type": "DIAGNOSTIC", "domains": ["sales"], "time_range": {}, "entities": []},
        "active_agents": ["sales"],
        "sales_findings": {"revenue_summary": {"revenue": 31525, "order_count": 230}},
        "inventory_findings": None,
        "marketing_findings": None,
        "support_findings": None,
        "reflection_notes": [],
        "confidence_score": 0.85,
        "gaps_identified": [],
        "reflection_passes": 0,
        "similar_incidents": [],
        "current_incident_id": None,
        "proposed_actions": [],
        "approved_actions": [],
        "executed_actions": [],
        "root_cause_analysis": "Revenue dropped due to 3 stockouts.",
        "recommendations": [],
        "final_response": None,
        "prior_context": None,
        "messages": [],
    }
    base.update(overrides)
    return base


# ── action_agent._get_valid_ids ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_valid_ids_success():
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_product_rows = MagicMock()
    mock_product_rows.fetchall.return_value = [("SKU-001",), ("SKU-002",)]
    mock_campaign_rows = MagicMock()
    mock_campaign_rows.fetchall.return_value = [("CAMP-001", "Summer Sale", "active")]
    mock_db.execute = AsyncMock(side_effect=[mock_product_rows, mock_campaign_rows])

    with patch("app.agents.action_agent.get_db_session", return_value=mock_db):
        from app.agents.action_agent import _get_valid_ids
        product_ids, campaign_info = await _get_valid_ids()

    assert "SKU-001" in product_ids
    assert "CAMP-001" in campaign_info


@pytest.mark.asyncio
async def test_get_valid_ids_db_failure():
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agents.action_agent.get_db_session", return_value=mock_db):
        from app.agents.action_agent import _get_valid_ids
        product_ids, campaign_info = await _get_valid_ids()

    assert product_ids == []
    assert "unavailable" in campaign_info


# ── propose_actions ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propose_actions_returns_list():
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_product_rows = MagicMock()
    mock_product_rows.fetchall.return_value = [("SKU-001",)]
    mock_campaign_rows = MagicMock()
    mock_campaign_rows.fetchall.return_value = []
    mock_db.execute = AsyncMock(side_effect=[mock_product_rows, mock_campaign_rows])

    mock_response = MagicMock()
    mock_response.text = json.dumps([{
        "action_type": "restock_product",
        "parameters": {"product_id": "SKU-001", "quantity": 100},
        "justification": "Out of stock",
        "impact_estimate": "Restores 30% revenue",
        "reversible": True,
    }])

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.agents.action_agent.get_db_session", return_value=mock_db):
        with patch("app.agents.action_agent.get_chat_llm", return_value=mock_llm):
            from app.agents.action_agent import propose_actions
            result = await propose_actions(_base_state())

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_propose_actions_handles_invalid_json():
    """When LLM returns non-JSON, propose_actions returns empty list."""
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(side_effect=Exception("DB unavail"))
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_response = MagicMock()
    mock_response.text = "I cannot propose any actions at this time."

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.agents.action_agent.get_db_session", return_value=mock_db):
        with patch("app.agents.action_agent.get_chat_llm", return_value=mock_llm):
            from app.agents.action_agent import propose_actions
            result = await propose_actions(_base_state())

    assert result == []


# ── memory.episodic ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_similar_incidents_success():
    mock_hit = MagicMock()
    mock_hit.payload = {
        "incident_id": "INC-001",
        "date": "2024-01-01T00:00:00Z",
        "query": "Why did sales drop?",
        "root_cause": "Stockouts",
        "domains": ["sales", "inventory"],
        "confidence": 0.87,
        "actions_taken": ["restock_product"],
    }
    mock_hit.score = 0.92

    mock_qdrant = AsyncMock()
    mock_qdrant.search = AsyncMock(return_value=[mock_hit])

    mock_ensure_collection = AsyncMock()

    with patch("app.memory.episodic.get_qdrant_client", return_value=mock_qdrant):
        with patch("app.memory.episodic.get_embeddings") as mock_emb:
            mock_emb.return_value.aembed_query = AsyncMock(return_value=[0.1] * 1536)
            with patch("app.db.qdrant.ensure_collection", new=AsyncMock()):
                from app.memory.episodic import retrieve_similar_incidents
                result = await retrieve_similar_incidents("Why did sales drop?")

    assert len(result) == 1
    assert result[0]["incident_id"] == "INC-001"
    assert result[0]["similarity_score"] == 0.92


@pytest.mark.asyncio
async def test_retrieve_similar_incidents_qdrant_unavailable_propagates():
    """When get_qdrant_client() raises, the exception propagates (caught by node layer)."""
    with patch("app.memory.episodic.get_qdrant_client", side_effect=Exception("Qdrant unavail")):
        from app.memory.episodic import retrieve_similar_incidents
        with pytest.raises(Exception, match="Qdrant unavail"):
            await retrieve_similar_incidents("test query")


@pytest.mark.asyncio
async def test_retrieve_similar_incidents_search_fails():
    mock_qdrant = AsyncMock()
    mock_qdrant.search = AsyncMock(side_effect=Exception("search error"))

    with patch("app.memory.episodic.get_qdrant_client", return_value=mock_qdrant):
        with patch("app.memory.episodic.get_embeddings") as mock_emb:
            mock_emb.return_value.aembed_query = AsyncMock(return_value=[0.1] * 1536)
            with patch("app.db.qdrant.ensure_collection", new=AsyncMock()):
                from app.memory.episodic import retrieve_similar_incidents
                result = await retrieve_similar_incidents("test query")
    assert result == []


def test_build_incident_text():
    from app.memory.episodic import _build_incident_text
    state = {
        "user_query": "Revenue drop?",
        "root_cause_analysis": "Stockouts caused 35% drop",
        "sales_findings": {"revenue": 31525},
        "inventory_findings": {"stockouts": 3},
        "marketing_findings": None,
        "support_findings": None,
    }
    result = _build_incident_text(state)
    assert "Revenue drop?" in result
    assert "root_cause" in result
    assert "sales_findings" in result
    assert "inventory_findings" in result


# ── memory.structured ────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_incident_list_empty(mock_db_session):
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.memory.structured.get_db_session", return_value=mock_db_session):
        from app.memory.structured import get_incident_list
        result = await get_incident_list()
    assert result == []


@pytest.mark.asyncio
async def test_get_incident_list_with_rows(mock_db_session):
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"id": "INC-001", "query": "Revenue drop", "confidence": 0.87}
    ]
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.memory.structured.get_db_session", return_value=mock_db_session):
        from app.memory.structured import get_incident_list
        result = await get_incident_list(limit=10)
    assert len(result) == 1
    assert result[0]["id"] == "INC-001"


@pytest.mark.asyncio
async def test_get_incident_by_id_not_found(mock_db_session):
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.memory.structured.get_db_session", return_value=mock_db_session):
        from app.memory.structured import get_incident_by_id
        result = await get_incident_by_id("MISSING")
    assert result is None


@pytest.mark.asyncio
async def test_get_incident_by_id_found(mock_db_session):
    mock_incident_result = MagicMock()
    mock_incident_result.mappings.return_value.first.return_value = {
        "id": "INC-001", "query": "Revenue drop"
    }
    mock_actions_result = MagicMock()
    mock_actions_result.mappings.return_value.all.return_value = []
    mock_db_session.execute = AsyncMock(side_effect=[mock_incident_result, mock_actions_result])

    with patch("app.memory.structured.get_db_session", return_value=mock_db_session):
        from app.memory.structured import get_incident_by_id
        result = await get_incident_by_id("INC-001")
    assert result is not None
    assert result["id"] == "INC-001"
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_store_action_outcome(mock_db_session):
    with patch("app.memory.structured.get_db_session", return_value=mock_db_session):
        from app.memory.structured import store_action_outcome
        await store_action_outcome(
            incident_id="INC-001",
            action_type="restock_product",
            parameters={"product_id": "SKU-001", "quantity": 100},
            approved=True,
            outcome="Restocked 100 units",
        )
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()


# ── graph/workflow ────────────────────────────────────────────────────────────

def test_build_graph_returns_state_graph():
    from app.graph.workflow import build_graph
    from langgraph.graph import StateGraph
    graph = build_graph()
    assert isinstance(graph, StateGraph)


def test_init_and_get_compiled_graph():
    from app.graph.workflow import init_compiled_graph, get_compiled_graph
    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    init_compiled_graph(checkpointer)

    compiled = get_compiled_graph()
    assert compiled is not None


def test_get_compiled_graph_raises_before_init():
    import app.graph.workflow as wf_module
    # Save current state and force None
    original = wf_module._compiled_graph
    wf_module._compiled_graph = None
    try:
        from app.core.exceptions import GraphNotInitializedError
        with pytest.raises(GraphNotInitializedError, match="not initialized"):
            wf_module.get_compiled_graph()
    finally:
        wf_module._compiled_graph = original


# ── action_tools: pause/resume campaign ──────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_action_pause_campaign_found():
    from app.tools.action_tools import execute_action

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    with patch("app.tools.action_tools.get_db_session", return_value=mock_db):
        result = await execute_action({
            "action_id": "ACT-4",
            "action_type": "pause_campaign",
            "parameters": {"campaign_id": "CAMP-001"},
        })
    assert result["success"] is True
    assert "CAMP-001" in result["message"]


@pytest.mark.asyncio
async def test_execute_action_resume_campaign_not_found():
    from app.tools.action_tools import execute_action

    mock_db_1 = AsyncMock()
    mock_db_1.__aenter__ = AsyncMock(return_value=mock_db_1)
    mock_db_1.__aexit__ = AsyncMock(return_value=False)
    mock_result_update = MagicMock()
    mock_result_update.rowcount = 0
    mock_db_1.execute = AsyncMock(return_value=mock_result_update)
    mock_db_1.commit = AsyncMock()

    mock_db_2 = AsyncMock()
    mock_db_2.__aenter__ = AsyncMock(return_value=mock_db_2)
    mock_db_2.__aexit__ = AsyncMock(return_value=False)
    mock_rows = MagicMock()
    mock_rows.fetchall.return_value = [("CAMP-002",), ("CAMP-003",)]
    mock_db_2.execute = AsyncMock(return_value=mock_rows)

    call_count = [0]

    async def side_effect_factory():
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_db_1
        return mock_db_2

    with patch("app.tools.action_tools.get_db_session", side_effect=lambda: [mock_db_1, mock_db_2][call_count[0] - 1 if call_count[0] > 0 else 0]):
        with patch("app.tools.action_tools.get_db_session") as mock_session:
            mock_session.side_effect = [mock_db_1, mock_db_2]
            result = await execute_action({
                "action_id": "ACT-5",
                "action_type": "resume_campaign",
                "parameters": {"campaign_id": "CAMP-MISSING"},
            })
    assert result["success"] is True  # execution didn't raise; returns "not found" message


# ── Chat route (sync endpoint) ────────────────────────────────────────────────

def test_build_initial_state():
    from app.api.routes.chat import _build_initial_state
    state = _build_initial_state("test query", "sess-1", "turn-1")
    assert state["user_query"] == "test query"
    assert state["session_id"] == "sess-1"
    assert state["intent"] is None
    assert state["messages"] == []


def test_chat_endpoint_sync():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.chat import router
    from app.api import deps

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "final_response": {"type": "diagnostic", "summary": "Revenue dropped."},
        "current_incident_id": "INC-001",
        "root_cause_analysis": "Stockouts",
        "proposed_actions": [],
    })

    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.dependency_overrides[deps.verify_token] = lambda: None
    app.dependency_overrides[deps.get_graph] = lambda: mock_graph

    with patch("app.core.observability.get_root_handler", return_value=None):
        client = TestClient(app)
        resp = client.post("/chat", json={
            "content": "Why did sales drop?",
            "session_id": "sess-test",
        })
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert "response" in body


def test_chat_endpoint_with_prior_context():
    """Follow-up chat uses persistent LangGraph thread (thread_id == session_id)."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.chat import router
    from app.api import deps

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "final_response": {"type": "diagnostic", "summary": "Follow-up response."},
        "current_incident_id": "INC-002",
        "root_cause_analysis": "Second analysis",
        "proposed_actions": [{"action_id": "ACT-1"}],
    })

    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.dependency_overrides[deps.verify_token] = lambda: None
    app.dependency_overrides[deps.get_graph] = lambda: mock_graph

    with patch("app.core.observability.get_root_handler", return_value=None):
        client = TestClient(app)
        resp = client.post("/chat", json={
            "content": "Follow-up question",
            "session_id": "sess-existing",
        })
    assert resp.status_code == 200
    # thread_id == session_id so LangGraph loads prior conversation via checkpointer
    call_config = mock_graph.ainvoke.call_args.kwargs["config"]
    assert call_config["configurable"]["thread_id"] == "sess-existing"


# ── Specialist agent nodes ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_run_sales_agent():
    from app.graph.nodes import node_run_sales_agent
    from langchain_core.messages import AIMessage

    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content='{"revenue_summary": {"revenue": 31525}}')]
    })

    with patch("app.graph.nodes.get_sales_agent", return_value=mock_agent):
        with patch("app.graph.nodes.get_callbacks", return_value=[]):
            result = await node_run_sales_agent(_base_state())
    assert "sales_findings" in result
    assert isinstance(result["sales_findings"], dict)


@pytest.mark.asyncio
async def test_node_run_inventory_agent():
    from app.graph.nodes import node_run_inventory_agent
    from langchain_core.messages import AIMessage

    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content='{"stockout_events": []}')]
    })

    with patch("app.graph.nodes.get_inventory_agent", return_value=mock_agent):
        with patch("app.graph.nodes.get_callbacks", return_value=[]):
            result = await node_run_inventory_agent(_base_state())
    assert "inventory_findings" in result


@pytest.mark.asyncio
async def test_node_run_marketing_agent():
    from app.graph.nodes import node_run_marketing_agent
    from langchain_core.messages import AIMessage

    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content='{"campaign_issues": []}')]
    })

    with patch("app.graph.nodes.get_marketing_agent", return_value=mock_agent):
        with patch("app.graph.nodes.get_callbacks", return_value=[]):
            result = await node_run_marketing_agent(_base_state())
    assert "marketing_findings" in result


@pytest.mark.asyncio
async def test_node_run_support_agent():
    from app.graph.nodes import node_run_support_agent
    from langchain_core.messages import AIMessage

    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={
        "messages": [AIMessage(content='{"ticket_summary": {"total_tickets": 187}}')]
    })

    with patch("app.graph.nodes.get_support_agent", return_value=mock_agent):
        with patch("app.graph.nodes.get_callbacks", return_value=[]):
            result = await node_run_support_agent(_base_state())
    assert "support_findings" in result
