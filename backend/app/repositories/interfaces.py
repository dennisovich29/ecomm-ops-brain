from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from app.models.domain import (
    AnomalyResult,
    CampaignMetric,
    ChannelPerformance,
    ActivePromotion,
    ComplaintTheme,
    DailyRevenue,
    ProductSales,
    RefundRateSummary,
    RegionalSales,
    RestockRecommendation,
    StockLevel,
    StockoutEvent,
    TicketVolumeSummary,
)


@runtime_checkable
class ISalesRepository(Protocol):
    async def get_daily_revenue(self, target_date: date) -> DailyRevenue: ...
    async def get_product_breakdown(self, target_date: date) -> list[ProductSales]: ...
    async def get_regional_breakdown(self, target_date: date) -> list[RegionalSales]: ...
    async def detect_anomaly(self, target_date: date, window_days: int = 30) -> AnomalyResult: ...
    async def compare_periods(self, target_date: date) -> dict: ...


@runtime_checkable
class IInventoryRepository(Protocol):
    async def get_stock_levels(self, product_ids: list[str] | None = None) -> list[StockLevel]: ...
    async def get_stockout_events(self, target_date: date) -> list[StockoutEvent]: ...
    async def get_restock_recommendations(self) -> list[RestockRecommendation]: ...
    async def get_views_vs_purchases(self, target_date: date) -> list[dict]: ...


@runtime_checkable
class IMarketingRepository(Protocol):
    async def get_campaign_metrics(self, target_date: date) -> list[CampaignMetric]: ...
    async def get_channel_performance(self, target_date: date) -> list[ChannelPerformance]: ...
    async def get_active_promotions(self) -> list[ActivePromotion]: ...


@runtime_checkable
class ISupportRepository(Protocol):
    async def get_ticket_volume(self, target_date: date) -> TicketVolumeSummary: ...
    async def get_refund_rates(self, target_date: date) -> RefundRateSummary: ...
    async def get_complaint_themes(self, target_date: date) -> list[ComplaintTheme]: ...
