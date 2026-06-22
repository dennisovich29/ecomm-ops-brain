"""Unit tests for domain tools and API routes."""
from __future__ import annotations

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.domain import (
    AnomalyResult, DailyRevenue, ProductSales, RegionalSales,
    StockLevel, StockoutEvent, RestockRecommendation,
    CampaignMetric, ChannelPerformance, ActivePromotion,
    TicketVolumeSummary, RefundRateSummary, ComplaintTheme,
)


YESTERDAY = str(date.today() - timedelta(days=1))
YESTERDAY_DATE = date.today() - timedelta(days=1)


# ── Sales tools ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_sales_repo():
    repo = MagicMock()
    repo.get_daily_revenue = AsyncMock(return_value=DailyRevenue(
        date=YESTERDAY_DATE,
        revenue=Decimal("31525.00"),
        order_count=230,
        avg_order_value=Decimal("137.07"),
        vs_prior_day_pct=-19.6,
        vs_prior_week_pct=-33.2,
    ))
    repo.detect_anomaly = AsyncMock(return_value=AnomalyResult(
        is_anomaly=True, z_score=-2.87, severity="high",
        description="Revenue is 2.87 standard deviations below the 30-day mean.",
    ))
    repo.get_product_breakdown = AsyncMock(return_value=[
        ProductSales(
            product_id="SKU-004", product_name="Coffee Grinder 500",
            category="Kitchen", units_sold=103, revenue=Decimal("14186.25"),
            revenue_contribution_pct=52.9,
        )
    ])
    repo.get_regional_breakdown = AsyncMock(return_value=[
        RegionalSales(region="North America", revenue=Decimal("15762.50"),
                      order_count=115, vs_baseline_pct=-35.0)
    ])
    repo.compare_periods = AsyncMock(return_value={
        "current": {}, "prior_week_same_day": {}, "revenue_delta_pct": -33.2
    })
    return repo


@pytest.mark.asyncio
async def test_sales_get_daily_revenue(mock_sales_repo):
    with patch("app.tools.sales_tools.get_sales_repo", return_value=mock_sales_repo):
        from app.tools.sales_tools import get_daily_revenue
        result = await get_daily_revenue.ainvoke({"target_date": YESTERDAY})
    assert float(result["revenue"]) == 31525.0
    assert result["order_count"] == 230


@pytest.mark.asyncio
async def test_sales_detect_anomaly(mock_sales_repo):
    with patch("app.tools.sales_tools.get_sales_repo", return_value=mock_sales_repo):
        from app.tools.sales_tools import detect_sales_anomaly
        result = await detect_sales_anomaly.ainvoke({"target_date": YESTERDAY})
    assert result["is_anomaly"] is True
    assert result["severity"] == "high"


@pytest.mark.asyncio
async def test_sales_product_breakdown(mock_sales_repo):
    with patch("app.tools.sales_tools.get_sales_repo", return_value=mock_sales_repo):
        from app.tools.sales_tools import get_product_sales_breakdown
        result = await get_product_sales_breakdown.ainvoke({"target_date": YESTERDAY})
    assert len(result) == 1
    assert result[0]["product_id"] == "SKU-004"


@pytest.mark.asyncio
async def test_sales_regional(mock_sales_repo):
    with patch("app.tools.sales_tools.get_sales_repo", return_value=mock_sales_repo):
        from app.tools.sales_tools import get_regional_sales
        result = await get_regional_sales.ainvoke({"target_date": YESTERDAY})
    assert len(result) == 1
    assert result[0]["region"] == "North America"


@pytest.mark.asyncio
async def test_sales_compare_periods(mock_sales_repo):
    with patch("app.tools.sales_tools.get_sales_repo", return_value=mock_sales_repo):
        from app.tools.sales_tools import compare_sales_periods
        result = await compare_sales_periods.ainvoke({"target_date": YESTERDAY})
    assert "revenue_delta_pct" in result


@pytest.mark.asyncio
async def test_sales_defaults_yesterday(mock_sales_repo):
    with patch("app.tools.sales_tools.get_sales_repo", return_value=mock_sales_repo):
        from app.tools.sales_tools import get_daily_revenue
        result = await get_daily_revenue.ainvoke({})
    assert result["order_count"] == 230


# ── Inventory tools ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_inventory_repo():
    repo = MagicMock()
    repo.get_stock_levels = AsyncMock(return_value=[
        StockLevel(product_id="SKU-001", product_name="Wireless Headphones Pro",
                   current_stock=0, reorder_point=50, days_of_stock=0.0, status="out_of_stock"),
        StockLevel(product_id="SKU-003", product_name="Smart Watch Elite",
                   current_stock=8, reorder_point=20, days_of_stock=1.5, status="critical"),
    ])
    repo.get_stockout_events = AsyncMock(return_value=[
        StockoutEvent(
            product_id="SKU-001", product_name="Wireless Headphones Pro",
            stockout_start=YESTERDAY, estimated_lost_revenue=Decimal("12000.00"),
        ),
    ])
    repo.get_restock_recommendations = AsyncMock(return_value=[
        RestockRecommendation(
            product_id="SKU-001", product_name="Wireless Headphones Pro",
            recommended_quantity=480, urgency="immediate",
            reason="Out of stock; immediate replenishment needed",
        ),
    ])
    repo.get_views_vs_purchases = AsyncMock(return_value=[
        {"product_id": "SKU-001", "views": 500, "purchases": 0}
    ])
    return repo


@pytest.mark.asyncio
async def test_inventory_get_stock_levels(mock_inventory_repo):
    with patch("app.tools.inventory_tools.get_inventory_repo", return_value=mock_inventory_repo):
        from app.tools.inventory_tools import get_stock_levels
        result = await get_stock_levels.ainvoke({})
    assert len(result) == 2
    statuses = {r["status"] for r in result}
    assert "out_of_stock" in statuses


@pytest.mark.asyncio
async def test_inventory_stockout_events(mock_inventory_repo):
    with patch("app.tools.inventory_tools.get_inventory_repo", return_value=mock_inventory_repo):
        from app.tools.inventory_tools import get_stockout_events
        result = await get_stockout_events.ainvoke({"target_date": YESTERDAY})
    assert len(result) == 1
    assert result[0]["product_id"] == "SKU-001"


@pytest.mark.asyncio
async def test_inventory_restock_recommendations(mock_inventory_repo):
    with patch("app.tools.inventory_tools.get_inventory_repo", return_value=mock_inventory_repo):
        from app.tools.inventory_tools import get_restock_recommendations
        result = await get_restock_recommendations.ainvoke({})
    assert len(result) == 1
    assert result[0]["urgency"] == "immediate"


@pytest.mark.asyncio
async def test_inventory_views_vs_purchases(mock_inventory_repo):
    with patch("app.tools.inventory_tools.get_inventory_repo", return_value=mock_inventory_repo):
        from app.tools.inventory_tools import get_views_vs_purchases
        result = await get_views_vs_purchases.ainvoke({"target_date": YESTERDAY})
    assert len(result) == 1
    assert result[0]["product_id"] == "SKU-001"


# ── Marketing tools ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_marketing_repo():
    repo = MagicMock()
    repo.get_campaign_metrics = AsyncMock(return_value=[
        CampaignMetric(
            campaign_id="CAMP-001", campaign_name="Summer Sale", channel="email",
            status="paused", spend=Decimal("1500.00"), impressions=120000,
            clicks=3600, conversions=180, roas=2.1, vs_prior_period_pct=-42.0,
        )
    ])
    repo.get_channel_performance = AsyncMock(return_value=[
        ChannelPerformance(channel="email", spend=Decimal("1500.00"),
                           revenue=Decimal("3150.00"), roas=2.1, vs_prior_week_pct=-30.0)
    ])
    repo.get_active_promotions = AsyncMock(return_value=[
        ActivePromotion(
            promotion_id="PROMO-001", name="Weekend Flash 20%", discount_pct=20.0,
            products=["SKU-001", "SKU-003"], status="missed", scheduled_at=YESTERDAY,
        )
    ])
    return repo


@pytest.mark.asyncio
async def test_marketing_campaign_metrics(mock_marketing_repo):
    with patch("app.tools.marketing_tools.get_marketing_repo", return_value=mock_marketing_repo):
        from app.tools.marketing_tools import get_campaign_metrics
        result = await get_campaign_metrics.ainvoke({"target_date": YESTERDAY})
    assert len(result) == 1
    assert result[0]["status"] == "paused"


@pytest.mark.asyncio
async def test_marketing_channel_performance(mock_marketing_repo):
    with patch("app.tools.marketing_tools.get_marketing_repo", return_value=mock_marketing_repo):
        from app.tools.marketing_tools import get_channel_performance
        result = await get_channel_performance.ainvoke({"target_date": YESTERDAY})
    assert result[0]["channel"] == "email"


@pytest.mark.asyncio
async def test_marketing_active_promotions(mock_marketing_repo):
    with patch("app.tools.marketing_tools.get_marketing_repo", return_value=mock_marketing_repo):
        from app.tools.marketing_tools import get_active_promotions
        result = await get_active_promotions.ainvoke({})
    assert result[0]["status"] == "missed"


# ── Support tools ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_support_repo():
    repo = MagicMock()
    repo.get_ticket_volume = AsyncMock(return_value=TicketVolumeSummary(
        date=YESTERDAY_DATE, total_tickets=187, vs_7day_avg=112.0,
        vs_7day_avg_pct=149.4, is_spike=True,
    ))
    repo.get_refund_rates = AsyncMock(return_value=RefundRateSummary(
        date=YESTERDAY_DATE, refund_rate_pct=12.5, return_rate_pct=8.3,
        vs_baseline_pct=185.7,
    ))
    repo.get_complaint_themes = AsyncMock(return_value=[
        ComplaintTheme(theme="defective_product", count=84, pct_of_total=44.9,
                       severity="high", sample_tickets=["Headphones stopped working"])
    ])
    return repo


@pytest.mark.asyncio
async def test_support_ticket_volume(mock_support_repo):
    with patch("app.tools.support_tools.get_support_repo", return_value=mock_support_repo):
        from app.tools.support_tools import get_ticket_volume
        result = await get_ticket_volume.ainvoke({"target_date": YESTERDAY})
    assert result["is_spike"] is True
    assert result["total_tickets"] == 187


@pytest.mark.asyncio
async def test_support_refund_rates(mock_support_repo):
    with patch("app.tools.support_tools.get_support_repo", return_value=mock_support_repo):
        from app.tools.support_tools import get_refund_rates
        result = await get_refund_rates.ainvoke({"target_date": YESTERDAY})
    assert result["refund_rate_pct"] == 12.5


@pytest.mark.asyncio
async def test_support_complaint_themes(mock_support_repo):
    with patch("app.tools.support_tools.get_support_repo", return_value=mock_support_repo):
        from app.tools.support_tools import get_complaint_themes
        result = await get_complaint_themes.ainvoke({"target_date": YESTERDAY})
    assert result[0]["severity"] == "high"


# ── Health/Ready routes ───────────────────────────────────────────────────────

def test_health_endpoint():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.health import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_endpoint_degraded():
    """When downstream services are unavailable, /ready returns degraded + 503."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.health import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "checks" in body


# ── Incidents routes ──────────────────────────────────────────────────────────

def test_incidents_list_empty():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.incidents import router
    from app.api import deps

    app = FastAPI()
    app.include_router(router, prefix="/incidents")
    app.dependency_overrides[deps.verify_token] = lambda: None

    with patch("app.memory.structured.get_incident_list", new=AsyncMock(return_value=[])):
        client = TestClient(app)
        resp = client.get("/incidents")
    assert resp.status_code == 200
    assert resp.json()["incidents"] == []


def test_incidents_list_with_data():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.incidents import router
    from app.api import deps

    app = FastAPI()
    app.include_router(router, prefix="/incidents")
    app.dependency_overrides[deps.verify_token] = lambda: None

    mock_data = [{"id": "INC-001", "description": "Revenue drop"}]
    with patch("app.memory.structured.get_incident_list", new=AsyncMock(return_value=mock_data)):
        client = TestClient(app)
        resp = client.get("/incidents")
    assert resp.status_code == 200
    assert len(resp.json()["incidents"]) == 1


def test_incidents_get_by_id_not_found():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.incidents import router
    from app.api import deps

    app = FastAPI()
    app.include_router(router, prefix="/incidents")
    app.dependency_overrides[deps.verify_token] = lambda: None

    with patch("app.memory.structured.get_incident_by_id", new=AsyncMock(return_value=None)):
        client = TestClient(app)
        resp = client.get("/incidents/INC-999")
    assert resp.status_code == 404


def test_incidents_get_by_id_found():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.incidents import router
    from app.api import deps

    app = FastAPI()
    app.include_router(router, prefix="/incidents")
    app.dependency_overrides[deps.verify_token] = lambda: None

    mock_inc = {"id": "INC-001", "description": "Revenue drop", "actions": []}
    with patch("app.memory.structured.get_incident_by_id", new=AsyncMock(return_value=mock_inc)):
        client = TestClient(app)
        resp = client.get("/incidents/INC-001")
    assert resp.status_code == 200
    assert resp.json()["incident"]["id"] == "INC-001"


# ── Actions routes ────────────────────────────────────────────────────────────

def test_actions_approve():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.actions import router
    from app.api import deps

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"executed_actions": [{"action_id": "ACT-001"}]})

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[deps.verify_token] = lambda: None
    app.dependency_overrides[deps.get_graph] = lambda: mock_graph

    client = TestClient(app)
    resp = client.post("/approve", json={
        "request_id": "REQ-001",
        "approved_action_ids": ["ACT-001"],
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "executed"
    assert resp.json()["request_id"] == "REQ-001"


def test_actions_decline():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.actions import router
    from app.api import deps

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={})

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[deps.verify_token] = lambda: None
    app.dependency_overrides[deps.get_graph] = lambda: mock_graph

    client = TestClient(app)
    resp = client.post("/decline", json={
        "request_id": "REQ-001",
        "reason": "Not authorized",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"


def test_actions_approve_not_found():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.actions import router
    from app.api import deps

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=ValueError("Thread not found"))

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[deps.verify_token] = lambda: None
    app.dependency_overrides[deps.get_graph] = lambda: mock_graph

    client = TestClient(app)
    resp = client.post("/approve", json={
        "request_id": "BAD",
        "approved_action_ids": [],
    })
    assert resp.status_code == 404


def test_actions_approve_server_error():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.routes.actions import router
    from app.api import deps

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Internal error"))

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[deps.verify_token] = lambda: None
    app.dependency_overrides[deps.get_graph] = lambda: mock_graph
    from app.core.exceptions import register_exception_handlers
    register_exception_handlers(app)

    client = TestClient(app)
    resp = client.post("/approve", json={
        "request_id": "ERR",
        "approved_action_ids": [],
    })
    assert resp.status_code == 500


# ── Repository factory ────────────────────────────────────────────────────────

def test_factory_returns_postgres_repos():
    """All factory functions return the postgres repository types."""
    from unittest.mock import patch, MagicMock

    fake_cls = MagicMock(return_value=MagicMock())

    with patch("app.repositories.postgres.sales.PostgresSalesRepository", fake_cls):
        from app.repositories.factory import get_sales_repo
        result = get_sales_repo()
        assert result is not None

    with patch("app.repositories.postgres.inventory.PostgresInventoryRepository", fake_cls):
        from app.repositories.factory import get_inventory_repo
        result = get_inventory_repo()
        assert result is not None

    with patch("app.repositories.postgres.marketing.PostgresMarketingRepository", fake_cls):
        from app.repositories.factory import get_marketing_repo
        result = get_marketing_repo()
        assert result is not None

    with patch("app.repositories.postgres.support.PostgresSupportRepository", fake_cls):
        from app.repositories.factory import get_support_repo
        result = get_support_repo()
        assert result is not None


# ── Middleware ────────────────────────────────────────────────────────────────

def test_agent_middleware_returns_list():
    """agent_middleware() returns a non-empty list of middleware items."""
    from unittest.mock import MagicMock
    from app.agents.middleware import agent_middleware
    mw = agent_middleware(MagicMock())
    assert isinstance(mw, list)
    assert len(mw) >= 2


def test_support_middleware_returns_list():
    """support_middleware() returns more middleware than agent_middleware (extra PII)."""
    from unittest.mock import MagicMock
    from app.agents.middleware import agent_middleware, support_middleware
    base = agent_middleware(MagicMock())
    support = support_middleware(MagicMock())
    # support stack has the 2 PII middlewares in addition to the base ones
    assert len(support) > len(base)


@pytest.mark.asyncio
async def test_resilient_tool_call_passes_on_success():
    """resilient_tool_call passes through the handler result on success."""
    from unittest.mock import MagicMock
    from app.agents.middleware import resilient_tool_call
    mock_request = MagicMock()
    expected = MagicMock()
    mock_handler = MagicMock(return_value=expected)
    # @wrap_tool_call on an async function exposes awrap_tool_call for the async path
    result = await resilient_tool_call.awrap_tool_call(mock_request, mock_handler)
    assert result is expected


@pytest.mark.asyncio
async def test_resilient_tool_call_returns_tool_message_on_error():
    """resilient_tool_call returns a ToolMessage instead of raising on handler error."""
    from unittest.mock import MagicMock
    from langchain.messages import ToolMessage
    from app.agents.middleware import resilient_tool_call
    mock_request = MagicMock()
    mock_request.tool_call = {"id": "call-123"}
    mock_handler = MagicMock(side_effect=RuntimeError("DB down"))
    result = await resilient_tool_call.awrap_tool_call(mock_request, mock_handler)
    assert isinstance(result, ToolMessage)
    assert "DB down" in result.content
    assert result.tool_call_id == "call-123"
