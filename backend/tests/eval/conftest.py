from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional

import pytest
from deepeval.models.base_model import DeepEvalBaseLLM

# Disable Deepeval cloud telemetry — run fully offline
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

_CASES_PATH = Path(__file__).parent / "test_cases.json"


# ── Azure OpenAI judge model ───────────────────────────────────────────────

class AzureJudgeLLM(DeepEvalBaseLLM):
    """Wraps the app's AzureChatOpenAI instance as a DeepEval judge model.

    DeepEval uses this to evaluate metrics (AnswerRelevancy, Faithfulness, etc.)
    instead of calling OpenAI directly, so we stay on the same Azure endpoint.
    """

    def __init__(self) -> None:
        # Import here so the module can be imported before env vars are set
        from langchain_openai import AzureChatOpenAI
        from app.core.config import get_settings
        s = get_settings()
        self._model = AzureChatOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            azure_deployment=s.azure_openai_deployment,
            api_key=s.azure_openai_api_key,
            api_version=s.azure_openai_api_version,
            temperature=0,
        )
        super().__init__()

    def load_model(self):
        return self._model

    def generate(self, prompt: str, schema=None) -> tuple[str, float]:
        response = self._model.invoke(prompt)
        return response.content, 0.0

    async def a_generate(self, prompt: str, schema=None) -> tuple[str, float]:
        response = await self._model.ainvoke(prompt)
        return response.content, 0.0

    def get_model_name(self) -> str:
        return "azure-gpt-4o"


# ── Shared fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def judge() -> AzureJudgeLLM:
    return AzureJudgeLLM()


@pytest.fixture(scope="session")
def test_cases() -> dict:
    return json.loads(_CASES_PATH.read_text())


@pytest.fixture(scope="session")
def full_bad_day_state() -> dict:
    """Complete OpsState for the 'bad yesterday' scenario — all four agents ran."""
    from datetime import date, timedelta
    yesterday = str(date.today() - timedelta(days=1))
    return {
        "user_query": "Why did sales drop yesterday?",
        "session_id": "eval-session-001",
        "turn_id": "eval-turn-001",
        "intent": {
            "query_type": "DIAGNOSTIC",
            "domains": ["sales", "inventory", "marketing", "support"],
            "time_range": {"start": yesterday, "end": yesterday},
            "entities": [],
        },
        "active_agents": ["sales", "inventory", "marketing", "support"],
        "sales_findings": {
            "revenue_summary": {
                "date": yesterday,
                "revenue": 31525.00,
                "vs_baseline_pct": -35.0,
                "orders": 230,
                "avg_order_value": 137.07,
            },
            "anomaly_result": {
                "is_anomaly": True,
                "z_score": -2.8,
                "severity": "high",
                "description": "Revenue 35% below 30-day average",
            },
            "top_affected_products": [
                {"product_id": "SKU-001", "name": "Wireless Headphones Pro", "revenue_drop_pct": -92},
                {"product_id": "SKU-002", "name": "Running Shoes X2", "revenue_drop_pct": -89},
                {"product_id": "SKU-003", "name": "Yoga Mat Premium", "revenue_drop_pct": -85},
            ],
        },
        "inventory_findings": {
            "stockout_events": [
                {"product_id": "SKU-001", "product_name": "Wireless Headphones Pro", "estimated_lost_revenue": 5200.00},
                {"product_id": "SKU-002", "product_name": "Running Shoes X2", "estimated_lost_revenue": 5200.00},
                {"product_id": "SKU-003", "product_name": "Yoga Mat Premium", "estimated_lost_revenue": 5200.00},
            ],
            "out_of_stock_count": 3,
            "total_estimated_lost_revenue": 15600.00,
        },
        "marketing_findings": {
            "campaign_issues": [
                {
                    "campaign_id": "CAMP-001",
                    "name": "Google Shopping — Electronics",
                    "status": "paused",
                    "spend": 0,
                    "roas": 0.0,
                    "vs_prior_period_pct": -100.0,
                }
            ],
            "missed_promotions": [
                {"promo_id": "PROMO-001", "name": "Summer Sale — 15% off Fitness", "status": "missed"}
            ],
        },
        "support_findings": {
            "ticket_volume": {"total_tickets": 110, "vs_7day_avg_pct": 129.2, "is_spike": True},
            "top_complaint_themes": [
                {"theme": "Out of stock / can't purchase", "ticket_count": 62, "pct_of_total": 55.4, "severity": "high"},
                {"theme": "Order delays", "ticket_count": 23, "pct_of_total": 20.9},
            ],
            "refund_rate": {"refund_rate_pct": 6.2, "vs_baseline_pct": 195.0},
        },
        "reflection_notes": ["Confidence 90% — sufficient evidence for synthesis."],
        "confidence_score": 0.9,
        "gaps_identified": [],
        "reflection_passes": 1,
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


# ── Full-graph fixture ─────────────────────────────────────────────────────

@pytest.fixture
async def compiled_graph():
    """Initialize the LangGraph compiled graph with a real PostgresSaver checkpointer.

    Used by TestFullGraph eval tests. Requires the Postgres container to be running.
    Function-scoped so each test gets its own event loop + connection (avoids
    asyncio.Lock bound-to-different-loop errors across pytest-asyncio per-test loops).
    """
    from app.core.config import get_settings
    from app.db.checkpointer import init_checkpointer, close_checkpointer
    from app.graph.workflow import init_compiled_graph, get_compiled_graph

    from app.core.config import get_settings
    from app.db.checkpointer import init_checkpointer, close_checkpointer
    from app.graph.workflow import init_compiled_graph, get_compiled_graph

    s = get_settings()
    checkpointer = await init_checkpointer(s.postgres_url_plain)
    init_compiled_graph(checkpointer)

    # Seed Qdrant with one historical incident so memory-recall tests have
    # something to retrieve (collection must exist before upserting).
    # Reset the Qdrant client singleton first — the previous test's event loop
    # is closed, so we must create a fresh client on the new loop.
    try:
        import app.db.qdrant as _qdrant_module
        if _qdrant_module._client is not None:
            try:
                await _qdrant_module._client.close()
            except Exception:
                pass
            _qdrant_module._client = None

        from app.db.qdrant import ensure_collection
        from app.memory.episodic import store_incident
        await ensure_collection()
        await store_incident({
            "user_query": "Why did sales drop last month?",
            "root_cause_analysis": (
                "Stockout of SKU-001 Wireless Headphones Pro caused a 35% revenue drop. "
                "Resolved by emergency restock of 500 units; revenue recovered within 2 days."
            ),
            "intent": {"domains": ["sales", "inventory"]},
            "confidence_score": 0.9,
            "executed_actions": [
                {"action_type": "restock_product",
                 "parameters": {"product_id": "SKU-001", "quantity": 500}}
            ],
        })
    except Exception as exc:
        import warnings
        warnings.warn(f"Qdrant seeding failed (memory test may degrade): {exc}")

    yield get_compiled_graph()

    await close_checkpointer()
