import pytest
from datetime import date, timedelta
from app.repositories.mock.sales import MockSalesRepository
from app.repositories.mock.inventory import MockInventoryRepository
from app.repositories.mock.marketing import MockMarketingRepository
from app.repositories.mock.support import MockSupportRepository


@pytest.mark.asyncio
async def test_sales_yesterday_is_anomaly():
    repo = MockSalesRepository()
    yesterday = date.today() - timedelta(days=1)
    anomaly = await repo.detect_anomaly(yesterday)
    assert anomaly.is_anomaly is True
    assert anomaly.severity == "high"


@pytest.mark.asyncio
async def test_inventory_stockout_events_yesterday():
    repo = MockInventoryRepository()
    yesterday = date.today() - timedelta(days=1)
    events = await repo.get_stockout_events(yesterday)
    assert len(events) == 3
    skus = {e.product_id for e in events}
    assert "SKU-001" in skus


@pytest.mark.asyncio
async def test_marketing_campaign_paused_yesterday():
    repo = MockMarketingRepository()
    yesterday = date.today() - timedelta(days=1)
    campaigns = await repo.get_campaign_metrics(yesterday)
    paused = [c for c in campaigns if c.status == "paused"]
    assert len(paused) >= 1


@pytest.mark.asyncio
async def test_support_ticket_spike_yesterday():
    repo = MockSupportRepository()
    yesterday = date.today() - timedelta(days=1)
    volume = await repo.get_ticket_volume(yesterday)
    assert volume.is_spike is True
    assert volume.vs_7day_avg_pct > 100
