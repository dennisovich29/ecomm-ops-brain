"""Tests for graph edges, memory modules, agent base, graph nodes helpers, and action tools."""
from __future__ import annotations

import json
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.graph.state import OpsState


# ── Helpers to build minimal OpsState ────────────────────────────────────────

def _base_state(**overrides) -> OpsState:
    base: OpsState = {
        "user_query": "What happened to sales yesterday?",
        "session_id": "test-session",
        "turn_id": "test-turn",
        "intent": {"query_type": "DIAGNOSTIC", "domains": ["sales"], "time_range": {}, "entities": []},
        "active_agents": ["sales"],
        "sales_findings": None,
        "inventory_findings": None,
        "marketing_findings": None,
        "support_findings": None,
        "reflection_notes": [],
        "confidence_score": 0.8,
        "gaps_identified": [],
        "reflection_passes": 0,
        "similar_incidents": [],
        "current_incident_id": None,
        "proposed_actions": [],
        "approved_actions": [],
        "executed_actions": [],
        "root_cause_analysis": "Revenue dropped 35% due to stockouts.",
        "recommendations": [],
        "final_response": None,
        "prior_context": None,
        "messages": [],
    }
    base.update(overrides)
    return base


# ── Graph edges ───────────────────────────────────────────────────────────────

class TestEdgeDispatchAgents:
    def test_general_intent_goes_to_format(self):
        from app.graph.edges import edge_dispatch_agents
        state = _base_state(intent={"query_type": "GENERAL", "domains": [], "time_range": {}, "entities": []})
        assert edge_dispatch_agents(state) == ["format_response"]

    def test_no_domains_goes_to_format(self):
        from app.graph.edges import edge_dispatch_agents
        state = _base_state(intent={"query_type": "DIAGNOSTIC", "domains": [], "time_range": {}, "entities": []})
        assert edge_dispatch_agents(state) == ["format_response"]

    def test_single_domain_dispatches(self):
        from app.graph.edges import edge_dispatch_agents
        state = _base_state(intent={"query_type": "DIAGNOSTIC", "domains": ["sales"], "time_range": {}, "entities": []})
        assert "run_sales_agent" in edge_dispatch_agents(state)

    def test_multiple_domains_dispatch(self):
        from app.graph.edges import edge_dispatch_agents
        state = _base_state(intent={"query_type": "DIAGNOSTIC",
                                    "domains": ["sales", "inventory", "marketing", "support"],
                                    "time_range": {}, "entities": []})
        result = edge_dispatch_agents(state)
        assert "run_sales_agent" in result
        assert "run_inventory_agent" in result

    def test_gaps_filter_on_re_query(self):
        from app.graph.edges import edge_dispatch_agents
        state = _base_state(
            intent={"query_type": "DIAGNOSTIC", "domains": ["sales", "inventory"], "time_range": {}, "entities": []},
            reflection_passes=1,
            gaps_identified=["inventory"],
        )
        result = edge_dispatch_agents(state)
        assert "run_inventory_agent" in result
        assert "run_sales_agent" not in result

    def test_gaps_all_resolved_goes_to_format(self):
        from app.graph.edges import edge_dispatch_agents
        state = _base_state(
            intent={"query_type": "DIAGNOSTIC", "domains": ["sales"], "time_range": {}, "entities": []},
            reflection_passes=1,
            gaps_identified=["marketing"],  # sales not in gaps
        )
        result = edge_dispatch_agents(state)
        assert result == ["format_response"]

    def test_unknown_domain_ignored(self):
        from app.graph.edges import edge_dispatch_agents
        state = _base_state(intent={"query_type": "DIAGNOSTIC", "domains": ["unknown_domain"],
                                    "time_range": {}, "entities": []})
        assert edge_dispatch_agents(state) == ["format_response"]


class TestEdgeAfterReflection:
    def test_summary_goes_to_format(self):
        from app.graph.edges import edge_after_reflection
        state = _base_state(intent={"query_type": "SUMMARY", "domains": ["sales"], "time_range": {}, "entities": []})
        assert edge_after_reflection(state) == "format_response"

    def test_diagnostic_defers_to_reflection_agent(self):
        from app.graph.edges import edge_after_reflection
        state = _base_state()
        with patch("app.agents.reflection_agent.should_re_query", return_value="synthesize_findings"):
            result = edge_after_reflection(state)
        assert result == "synthesize_findings"


class TestEdgeAfterSynthesis:
    def test_diagnostic_goes_to_format(self):
        from app.graph.edges import edge_after_synthesis
        state = _base_state(intent={"query_type": "DIAGNOSTIC", "domains": [], "time_range": {}, "entities": []})
        assert edge_after_synthesis(state) == "format_response"

    def test_action_goes_to_propose(self):
        from app.graph.edges import edge_after_synthesis
        state = _base_state(intent={"query_type": "ACTION", "domains": [], "time_range": {}, "entities": []})
        assert edge_after_synthesis(state) == "propose_actions"

    def test_hybrid_goes_to_propose(self):
        from app.graph.edges import edge_after_synthesis
        state = _base_state(intent={"query_type": "HYBRID", "domains": [], "time_range": {}, "entities": []})
        assert edge_after_synthesis(state) == "propose_actions"


class TestEdgeAfterHitl:
    def test_approved_actions_execute(self):
        from app.graph.edges import edge_after_hitl
        state = _base_state(approved_actions=[{"action_id": "ACT-001"}])
        assert edge_after_hitl(state) == "execute_actions"

    def test_no_approved_actions_format(self):
        from app.graph.edges import edge_after_hitl
        state = _base_state(approved_actions=[])
        assert edge_after_hitl(state) == "format_response"


class TestEdgeAfterExecution:
    def test_always_store_incident(self):
        from app.graph.edges import edge_after_execution
        state = _base_state()
        assert edge_after_execution(state) == "store_incident"


# ── Graph nodes helpers ────────────────────────────────────────────────────────

def test_parse_findings_valid_json():
    from app.graph.nodes import _parse_findings
    content = 'Preamble {"revenue": 100, "orders": 50} Postamble'
    result = _parse_findings(content)
    assert result == {"revenue": 100, "orders": 50}


def test_parse_findings_fallback_to_raw():
    from app.graph.nodes import _parse_findings
    content = "No JSON here, just plain text"
    result = _parse_findings(content)
    assert result == {"raw": "No JSON here, just plain text"}


def test_extract_last_content_with_messages():
    from app.graph.nodes import _extract_last_content
    from langchain_core.messages import AIMessage, HumanMessage
    messages = [HumanMessage(content="question"), AIMessage(content="answer")]
    assert _extract_last_content(messages) == "answer"


def test_extract_last_content_empty():
    from app.graph.nodes import _extract_last_content
    assert _extract_last_content([]) == ""


def test_build_incident_text_minimal():
    from app.graph.nodes import _build_incident_text
    state = _base_state()
    result = _build_incident_text(state)
    assert "What happened to sales yesterday?" in result


def test_build_incident_text_with_findings():
    from app.graph.nodes import _build_incident_text
    state = _base_state(sales_findings={"revenue": 100}, inventory_findings={"stockouts": []})
    result = _build_incident_text(state)
    assert "sales" in result
    assert "inventory" in result


# ── Format response (pure / non-LLM paths) ───────────────────────────────────

@pytest.mark.asyncio
async def test_format_response_diagnostic():
    from app.graph.nodes import node_format_response
    state = _base_state(
        intent={"query_type": "DIAGNOSTIC", "domains": ["sales"], "time_range": {}, "entities": []},
        root_cause_analysis="Revenue dropped due to stockouts.",
    )
    result = await node_format_response(state)
    assert result["final_response"]["type"] == "diagnostic"
    assert "stockouts" in result["final_response"]["summary"]


@pytest.mark.asyncio
async def test_format_response_action_executed():
    from app.graph.nodes import node_format_response
    state = _base_state(
        intent={"query_type": "ACTION", "domains": [], "time_range": {}, "entities": []},
        executed_actions=[{"action_id": "ACT-1", "success": True, "message": "Done"}],
    )
    result = await node_format_response(state)
    assert result["final_response"]["type"] == "action_executed"
    assert "1 action(s) executed" in result["final_response"]["summary"]


@pytest.mark.asyncio
async def test_format_response_memory():
    from app.graph.nodes import node_format_response
    state = _base_state(
        intent={"query_type": "MEMORY", "domains": [], "time_range": {}, "entities": []},
        similar_incidents=[{"id": "INC-1"}],
    )
    result = await node_format_response(state)
    assert result["final_response"]["type"] == "memory_recall"
    assert "1 similar" in result["final_response"]["summary"]


@pytest.mark.asyncio
async def test_format_response_summary_empty():
    from app.graph.nodes import node_format_response
    state = _base_state(
        intent={"query_type": "SUMMARY", "domains": ["sales"], "time_range": {}, "entities": []},
    )
    result = await node_format_response(state)
    assert result["final_response"]["type"] == "summary"
    assert "No significant findings" in result["final_response"]["summary"]


@pytest.mark.asyncio
async def test_format_response_summary_with_findings():
    from app.graph.nodes import node_format_response
    state = _base_state(
        intent={"query_type": "SUMMARY", "domains": ["inventory", "sales"], "time_range": {}, "entities": []},
        inventory_findings={
            "stockout_events": [{"product_id": "SKU-001", "product_name": "Headphones",
                                  "estimated_lost_revenue": "12000", "stockout_start": "2024-01-01"}],
            "low_stock_products": [],
            "restock_recommendations": [],
        },
        sales_findings={
            "revenue_summary": {"revenue": "31525", "order_count": 230,
                                  "avg_order_value": "137", "vs_prior_day_pct": -19.6,
                                  "vs_prior_week_pct": -33.2},
            "anomaly_result": {"is_anomaly": True, "description": "Below mean"},
            "top_affected_products": [],
        },
    )
    result = await node_format_response(state)
    assert result["final_response"]["type"] == "summary"
    summary = result["final_response"]["summary"]
    assert "Inventory" in summary or "Sales" in summary


# ── Node: execute_actions ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_execute_actions():
    from app.graph.nodes import node_execute_actions
    mock_result = {"action_id": "ACT-1", "success": True, "message": "Done", "action_type": "restock_product"}

    with patch("app.tools.action_tools.execute_action", new=AsyncMock(return_value=mock_result)):
        state = _base_state(approved_actions=[{"action_id": "ACT-1", "action_type": "restock_product"}])
        result = await node_execute_actions(state)
    assert len(result["executed_actions"]) == 1
    assert result["executed_actions"][0]["success"] is True


@pytest.mark.asyncio
async def test_node_execute_actions_empty():
    from app.graph.nodes import node_execute_actions
    state = _base_state(approved_actions=[])
    result = await node_execute_actions(state)
    assert result["executed_actions"] == []


# ── Node: store_incident ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_store_incident_success():
    from app.graph.nodes import node_store_incident
    with patch("app.memory.episodic.store_incident", new=AsyncMock(return_value="INC-001")):
        result = await node_store_incident(_base_state())
    assert result["current_incident_id"] == "INC-001"


@pytest.mark.asyncio
async def test_node_store_incident_failure_returns_empty():
    from app.graph.nodes import node_store_incident
    with patch("app.memory.episodic.store_incident", new=AsyncMock(side_effect=Exception("DB down"))):
        result = await node_store_incident(_base_state())
    assert result == {}


# ── Node: retrieve_memory ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_retrieve_memory_success():
    from app.graph.nodes import node_retrieve_memory
    mock_incidents = [{"id": "INC-001", "query": "Revenue dropped"}]
    with patch("app.memory.episodic.retrieve_similar_incidents", new=AsyncMock(return_value=mock_incidents)):
        result = await node_retrieve_memory(_base_state())
    assert result["similar_incidents"] == mock_incidents


@pytest.mark.asyncio
async def test_node_retrieve_memory_failure_returns_empty():
    from app.graph.nodes import node_retrieve_memory
    with patch("app.memory.episodic.retrieve_similar_incidents",
               new=AsyncMock(side_effect=Exception("Qdrant down"))):
        result = await node_retrieve_memory(_base_state())
    assert result["similar_incidents"] == []


# ── Node: run_reflection ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_run_reflection():
    from app.graph.nodes import node_run_reflection
    with patch("app.agents.reflection_agent.reflect",
               return_value={"reflection_notes": ["gap: inventory"], "gaps_identified": ["inventory"],
                              "confidence_score": 0.6, "reflection_passes": 1}):
        result = await node_run_reflection(_base_state())
    assert "reflection_notes" in result


# ── Action tools ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_action_unknown_type():
    from app.tools.action_tools import execute_action
    result = await execute_action({"action_id": "ACT-1", "action_type": "unknown_action", "parameters": {}})
    assert result["success"] is False
    assert "Unknown action type" in result["message"]


@pytest.mark.asyncio
async def test_execute_action_restock_success():
    from app.tools.action_tools import execute_action

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.tools.action_tools.get_db_session", return_value=mock_db):
        result = await execute_action({
            "action_id": "ACT-1",
            "action_type": "restock_product",
            "parameters": {"product_id": "SKU-001", "quantity": 100},
        })
    assert result["success"] is True
    assert "SKU-001" in result["message"]


@pytest.mark.asyncio
async def test_execute_action_db_failure_returns_false():
    from app.tools.action_tools import execute_action

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tools.action_tools.get_db_session", return_value=mock_db):
        result = await execute_action({
            "action_id": "ACT-1",
            "action_type": "restock_product",
            "parameters": {"product_id": "SKU-001", "quantity": 50},
        })
    assert result["success"] is False
    assert "failed" in result["message"].lower()


@pytest.mark.asyncio
async def test_execute_action_apply_discount():
    from app.tools.action_tools import execute_action

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.tools.action_tools.get_db_session", return_value=mock_db):
        result = await execute_action({
            "action_id": "ACT-2",
            "action_type": "apply_discount",
            "parameters": {"product_id": "SKU-001", "discount_pct": 15},
        })
    assert result["success"] is True
    assert "15.0%" in result["message"]


@pytest.mark.asyncio
async def test_execute_action_create_support_ticket():
    from app.tools.action_tools import execute_action

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.tools.action_tools.get_db_session", return_value=mock_db):
        result = await execute_action({
            "action_id": "ACT-3",
            "action_type": "create_support_ticket",
            "parameters": {"issue_type": "defective_product", "description": "Broken headphones"},
        })
    assert result["success"] is True
    assert "defective_product" in result["message"]


# ── Node: route_intent ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_route_intent_fresh():
    from app.graph.nodes import node_route_intent
    from langchain_core.runnables import RunnableLambda

    mock_intent = {
        "query_type": "DIAGNOSTIC",
        "domains": ["sales"],
        "time_range": {"start": "2024-01-01", "end": "2024-01-01"},
        "entities": [],
    }

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = RunnableLambda(
        lambda _: MagicMock(
            query_type="DIAGNOSTIC",
            domains=["sales"],
            time_range={"start": "2024-01-01", "end": "2024-01-01"},
            entities=[],
        )
    )

    with patch("app.agents.intent_router.get_chat_llm", return_value=mock_llm):
        state = _base_state(reflection_passes=0)
        result = await node_route_intent(state)

    assert "intent" in result
    assert "active_agents" in result
    # Fresh turn resets findings
    assert result.get("sales_findings") is None
