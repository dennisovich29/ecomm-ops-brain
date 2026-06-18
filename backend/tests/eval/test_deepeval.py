"""DeepEval-based LLM evaluation tests.

Run with:
    cd backend && pytest tests/eval/ -v -m eval

Or via make:
    make eval

These tests make real LLM calls (Azure OpenAI) and are intentionally slower
than unit tests. They validate that LLM components produce correct, faithful,
and hallucination-free outputs against the known "bad yesterday" mock scenario.
"""
from __future__ import annotations

import json
import os
import pytest

from deepeval import assert_test
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
    GEval,
)

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

pytestmark = pytest.mark.eval


# ── Helpers ────────────────────────────────────────────────────────────────

def _intent_to_str(intent: dict) -> str:
    return json.dumps(intent, indent=2)


# ══════════════════════════════════════════════════════════════════════════
# 1. Intent Routing — GEval (classification accuracy)
# ══════════════════════════════════════════════════════════════════════════

class TestIntentRouting:
    """Verify the intent router classifies query_type and domains correctly."""

    @pytest.fixture(autouse=True)
    def _metric(self, judge):
        self.metric = GEval(
            name="Intent Classification Accuracy",
            criteria=(
                "The actual output is a JSON intent object. "
                "It should have the correct query_type matching the expected output, "
                "and its domains list should include all domains mentioned in the expected output. "
                "Deduct points if query_type is wrong or required domains are missing."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            threshold=0.7,
        )

    @pytest.mark.asyncio
    async def test_diagnostic_sales_drop(self, test_cases):
        case = next(c for c in test_cases["intent_cases"] if c["id"] == "intent_diagnostic_sales_drop")
        from app.agents.intent_router import route_intent
        intent = await route_intent(case["input"], session_id="eval-intent-diag")
        tc = LLMTestCase(
            input=case["input"],
            actual_output=_intent_to_str(intent),
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.metric])

    @pytest.mark.asyncio
    async def test_action_fix_stockout(self, test_cases):
        case = next(c for c in test_cases["intent_cases"] if c["id"] == "intent_action_fix_stockout")
        from app.agents.intent_router import route_intent
        intent = await route_intent(case["input"], session_id="eval-intent-action")
        assert intent["query_type"] == "ACTION", f"Expected ACTION, got {intent['query_type']}"
        tc = LLMTestCase(
            input=case["input"],
            actual_output=_intent_to_str(intent),
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.metric])

    @pytest.mark.asyncio
    async def test_memory_past_incidents(self, test_cases):
        case = next(c for c in test_cases["intent_cases"] if c["id"] == "intent_memory_past_incidents")
        from app.agents.intent_router import route_intent
        intent = await route_intent(case["input"], session_id="eval-intent-memory")
        assert intent["query_type"] == "MEMORY", f"Expected MEMORY, got {intent['query_type']}"
        tc = LLMTestCase(
            input=case["input"],
            actual_output=_intent_to_str(intent),
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.metric])

    @pytest.mark.asyncio
    async def test_hybrid_analyze_and_fix(self, test_cases):
        case = next(c for c in test_cases["intent_cases"] if c["id"] == "intent_hybrid_analyze_and_fix")
        from app.agents.intent_router import route_intent
        intent = await route_intent(case["input"], session_id="eval-intent-hybrid")
        tc = LLMTestCase(
            input=case["input"],
            actual_output=_intent_to_str(intent),
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.metric])

    @pytest.mark.asyncio
    async def test_summary_report(self, test_cases):
        case = next(c for c in test_cases["intent_cases"] if c["id"] == "intent_summary_report")
        from app.agents.intent_router import route_intent
        intent = await route_intent(case["input"], session_id="eval-intent-summary")
        tc = LLMTestCase(
            input=case["input"],
            actual_output=_intent_to_str(intent),
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.metric])


# ══════════════════════════════════════════════════════════════════════════
# 2. Synthesis / Root Cause Analysis
# ══════════════════════════════════════════════════════════════════════════

class TestSynthesis:
    """Verify synthesize_findings produces faithful, relevant, non-hallucinating RCAs."""

    @pytest.fixture(autouse=True)
    def _metrics(self, judge):
        self.relevancy = AnswerRelevancyMetric(threshold=0.7, model=judge)
        self.faithfulness = FaithfulnessMetric(threshold=0.7, model=judge)
        self.hallucination = HallucinationMetric(threshold=0.4, model=judge)

    @pytest.mark.asyncio
    async def test_full_findings_rca(self, test_cases, full_bad_day_state):
        """Full agent findings → RCA must mention stockout + campaign pause, stay faithful."""
        case = next(c for c in test_cases["synthesis_cases"] if c["id"] == "synthesis_full_findings")
        from app.graph.nodes import node_synthesize_findings
        result = await node_synthesize_findings(full_bad_day_state)
        rca = result["root_cause_analysis"]

        tc = LLMTestCase(
            input=case["input"],
            actual_output=rca,
            expected_output=(
                "Root cause: stockout of top 3 SKUs (SKU-001 Wireless Headphones Pro, "
                "SKU-002 Running Shoes X2, SKU-003 Yoga Mat Premium) combined with the "
                "Google Shopping campaign (CAMP-001) being paused. Contributing factors: "
                "support ticket spike of 129% dominated by out-of-stock complaints, "
                "refund rate up 195%."
            ),
            context=case["context"],
            retrieval_context=case["context"],
        )
        assert_test(tc, [self.relevancy, self.faithfulness, self.hallucination])

    @pytest.mark.asyncio
    async def test_partial_findings_rca(self, test_cases, full_bad_day_state):
        """Partial findings (sales only) → RCA must NOT claim confirmed stockout/campaign causes."""
        case = next(c for c in test_cases["synthesis_cases"] if c["id"] == "synthesis_partial_findings_sales_only")
        partial_state = {
            **full_bad_day_state,
            "inventory_findings": None,
            "marketing_findings": None,
            "support_findings": None,
            "confidence_score": 0.4,
            "intent": {**full_bad_day_state["intent"], "domains": ["sales"]},
        }
        from app.graph.nodes import node_synthesize_findings
        result = await node_synthesize_findings(partial_state)
        rca = result["root_cause_analysis"]

        forbidden = case["should_not_contain"]
        for phrase in forbidden:
            assert phrase.lower() not in rca.lower(), (
                f"RCA hallucinated '{phrase}' without supporting data:\n{rca}"
            )

        tc = LLMTestCase(
            input=case["input"],
            actual_output=rca,
            expected_output=(
                "Revenue dropped 35%, anomaly confirmed. "
                "Exact root cause unclear without inventory, marketing, and support data."
            ),
            context=case["context"],
            retrieval_context=case["context"],
        )
        assert_test(tc, [self.relevancy, self.hallucination])

    @pytest.mark.asyncio
    async def test_synthesis_with_memory_context(self, test_cases, full_bad_day_state):
        """RCA with historical incident in state → should reference past incident."""
        case = next(c for c in test_cases["synthesis_cases"] if c["id"] == "synthesis_with_memory_context")
        state_with_memory = {
            **full_bad_day_state,
            "inventory_findings": case["agent_findings"]["inventory"],
            "marketing_findings": None,
            "support_findings": None,
            "similar_incidents": case["similar_incidents"],
            "confidence_score": 0.65,
        }
        from app.graph.nodes import node_synthesize_findings
        result = await node_synthesize_findings(state_with_memory)
        rca = result["root_cause_analysis"]

        tc = LLMTestCase(
            input=case["input"],
            actual_output=rca,
            expected_output=(
                "SKU-001 stockout confirmed. Similar incident on 2025-11-15 resolved by "
                "restocking 500 units; revenue recovered within 2 days."
            ),
            context=case["context"],
            retrieval_context=case["context"],
        )
        assert_test(tc, [self.relevancy, self.faithfulness])


# ══════════════════════════════════════════════════════════════════════════
# 3. Action Proposals
# ══════════════════════════════════════════════════════════════════════════

class TestActionProposals:
    """Verify action_agent proposes relevant, justified actions for the given state."""

    @pytest.fixture(autouse=True)
    def _metric(self, judge):
        self.metric = GEval(
            name="Action Proposal Quality",
            criteria=(
                "The actual output is a JSON list of proposed actions. "
                "Each action must have action_type, parameters, and justification. "
                "The action_types proposed should match those described in the expected output. "
                "Justifications must reference specific data from the input state (product IDs, "
                "campaign IDs, revenue figures). Deduct points for vague or unjustified actions."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            threshold=0.7,
        )

    @pytest.mark.asyncio
    async def test_action_proposal_three_stockouts(self, test_cases, full_bad_day_state):
        """3 stockout SKUs + paused campaign → restock × 3 + resume_campaign."""
        case = next(c for c in test_cases["action_cases"] if c["id"] == "action_proposal_stockout_three_skus")
        action_state = {**full_bad_day_state, "intent": {**full_bad_day_state["intent"], "query_type": "ACTION"}}
        from app.agents.action_agent import propose_actions
        actions = await propose_actions(action_state)
        actions_json = json.dumps([a.model_dump() if hasattr(a, "model_dump") else a for a in actions], indent=2)

        proposed_types = {
            (a.action_type if hasattr(a, "action_type") else a.get("action_type"))
            for a in actions
        }
        assert "restock_product" in proposed_types, f"Expected restock_product in {proposed_types}"

        tc = LLMTestCase(
            input=case["input"],
            actual_output=actions_json,
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.metric])

    @pytest.mark.asyncio
    async def test_action_proposal_campaign_only(self, test_cases, full_bad_day_state):
        """Only paused campaign in state → must propose resume_campaign."""
        case = next(c for c in test_cases["action_cases"] if c["id"] == "action_proposal_campaign_only")
        campaign_only_state = {
            **full_bad_day_state,
            "inventory_findings": {"stockout_events": [], "out_of_stock_count": 0},
            "intent": {**full_bad_day_state["intent"], "query_type": "ACTION", "domains": ["marketing"]},
        }
        from app.agents.action_agent import propose_actions
        actions = await propose_actions(campaign_only_state)
        actions_json = json.dumps([a.model_dump() if hasattr(a, "model_dump") else a for a in actions], indent=2)

        proposed_types = {
            (a.action_type if hasattr(a, "action_type") else a.get("action_type"))
            for a in actions
        }
        assert "resume_campaign" in proposed_types, f"Expected resume_campaign in {proposed_types}"

        tc = LLMTestCase(
            input=case["input"],
            actual_output=actions_json,
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.metric])


# ══════════════════════════════════════════════════════════════════════════
# 4. Full Graph — End-to-End
# ══════════════════════════════════════════════════════════════════════════

class TestFullGraph:
    """Run the complete LangGraph workflow and evaluate the final response."""

    @pytest.fixture(autouse=True)
    def _metrics(self, judge):
        self.relevancy = AnswerRelevancyMetric(threshold=0.7, model=judge)
        self.faithfulness = FaithfulnessMetric(threshold=0.7, model=judge)
        self.hallucination = HallucinationMetric(threshold=0.4, model=judge)

    @pytest.mark.asyncio
    async def test_diagnostic_full_graph(self, test_cases):
        """Full graph run for diagnostic query should identify stockout + campaign root cause."""
        case = next(c for c in test_cases["graph_cases"] if c["id"] == "graph_diagnostic_full")
        from app.graph.workflow import get_compiled_graph
        import uuid
        from datetime import date, timedelta

        yesterday = str(date.today() - timedelta(days=1))
        graph = get_compiled_graph()
        state = {
            "user_query": case["input"],
            "session_id": "eval-graph-diag",
            "turn_id": str(uuid.uuid4()),
            "intent": None,
            "active_agents": [],
            "sales_findings": None,
            "inventory_findings": None,
            "marketing_findings": None,
            "support_findings": None,
            "reflection_notes": [],
            "confidence_score": 0.0,
            "gaps_identified": [],
            "reflection_passes": 0,
            "similar_incidents": [],
            "current_incident_id": None,
            "proposed_actions": [],
            "approved_actions": [],
            "executed_actions": [],
            "hitl_workflow_id": None,
            "awaiting_approval": False,
            "root_cause_analysis": None,
            "recommendations": [],
            "final_response": None,
            "messages": [],
        }
        config = {"configurable": {"thread_id": "eval-graph-diag"}}
        result = await graph.ainvoke(state, config=config)

        final = result.get("final_response", {})
        assert final.get("type") == "diagnostic", f"Expected diagnostic response, got: {final.get('type')}"

        rca = result.get("root_cause_analysis", "") or ""
        tc = LLMTestCase(
            input=case["input"],
            actual_output=rca,
            expected_output=case["expected_output"],
            context=case["context"],
            retrieval_context=case["context"],
        )
        assert_test(tc, [self.relevancy, self.faithfulness, self.hallucination])

    @pytest.mark.asyncio
    async def test_memory_query_graph(self, test_cases):
        """Memory query should return a memory_recall response type."""
        case = next(c for c in test_cases["graph_cases"] if c["id"] == "graph_memory_query")
        from app.graph.workflow import get_compiled_graph
        import uuid

        graph = get_compiled_graph()
        state = {
            "user_query": case["input"],
            "session_id": "eval-graph-mem",
            "turn_id": str(uuid.uuid4()),
            "intent": None,
            "active_agents": [],
            "sales_findings": None,
            "inventory_findings": None,
            "marketing_findings": None,
            "support_findings": None,
            "reflection_notes": [],
            "confidence_score": 0.0,
            "gaps_identified": [],
            "reflection_passes": 0,
            "similar_incidents": [],
            "current_incident_id": None,
            "proposed_actions": [],
            "approved_actions": [],
            "executed_actions": [],
            "hitl_workflow_id": None,
            "awaiting_approval": False,
            "root_cause_analysis": None,
            "recommendations": [],
            "final_response": None,
            "messages": [],
        }
        config = {"configurable": {"thread_id": "eval-graph-mem"}}
        result = await graph.ainvoke(state, config=config)

        final = result.get("final_response", {})
        assert final.get("type") == "memory_recall", f"Expected memory_recall, got: {final.get('type')}"

        summary = final.get("summary", "")
        tc = LLMTestCase(
            input=case["input"],
            actual_output=summary,
            expected_output=case["expected_output"],
        )
        assert_test(tc, [self.relevancy])
