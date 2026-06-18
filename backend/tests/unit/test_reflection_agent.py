import pytest
from app.agents.reflection_agent import reflect


def _base_state(**kwargs):
    return {
        "user_query": "Why did sales drop yesterday?",
        "intent": {"query_type": "DIAGNOSTIC", "domains": ["sales", "inventory"], "time_range": {}, "entities": []},
        "sales_findings": None,
        "inventory_findings": None,
        "marketing_findings": None,
        "support_findings": None,
        "reflection_passes": 0,
        "gaps_identified": [],
        "reflection_notes": [],
        "confidence_score": 0.0,
        **kwargs,
    }


def test_low_confidence_when_no_findings():
    state = _base_state()
    result = reflect(state)
    assert result["confidence_score"] < 0.7
    assert "missing_sales_data" in result["gaps_identified"]
    assert "missing_inventory_data" in result["gaps_identified"]


def test_high_confidence_with_corroborating_findings():
    state = _base_state(
        sales_findings={"revenue_summary": {"revenue": 31525}, "anomaly_result": {"is_anomaly": True}},
        inventory_findings={"stockout_events": [{"product_id": "SKU-001"}]},
        marketing_findings={"campaign_issues": [{"status": "paused"}]},
        support_findings={"top_complaint_themes": [{"theme": "out of stock"}]},
    )
    result = reflect(state)
    assert result["confidence_score"] >= 0.7
    assert result["gaps_identified"] == []


def test_passes_increment():
    state = _base_state()
    result = reflect(state)
    assert result["reflection_passes"] == 1
