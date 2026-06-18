from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ── Sales ────────────────────────────────────────────────────────────────────

class DailyRevenue(BaseModel):
    date: date
    revenue: Decimal
    order_count: int
    avg_order_value: Decimal
    vs_prior_day_pct: Optional[float] = None
    vs_prior_week_pct: Optional[float] = None


class ProductSales(BaseModel):
    product_id: str
    product_name: str
    category: str
    units_sold: int
    revenue: Decimal
    revenue_contribution_pct: float


class RegionalSales(BaseModel):
    region: str
    revenue: Decimal
    order_count: int
    vs_baseline_pct: float


class AnomalyResult(BaseModel):
    is_anomaly: bool
    z_score: float
    severity: str  # "low" | "medium" | "high"
    description: str


# ── Inventory ────────────────────────────────────────────────────────────────

class StockLevel(BaseModel):
    product_id: str
    product_name: str
    current_stock: int
    reorder_point: int
    days_of_stock: float
    status: str  # "ok" | "low" | "critical" | "out_of_stock"


class StockoutEvent(BaseModel):
    product_id: str
    product_name: str
    stockout_start: str
    stockout_end: Optional[str] = None
    estimated_lost_revenue: Decimal


class RestockRecommendation(BaseModel):
    product_id: str
    product_name: str
    recommended_quantity: int
    urgency: str  # "immediate" | "soon" | "planned"
    reason: str


# ── Marketing ────────────────────────────────────────────────────────────────

class CampaignMetric(BaseModel):
    campaign_id: str
    campaign_name: str
    channel: str
    status: str  # "active" | "paused" | "ended"
    spend: Decimal
    impressions: int
    clicks: int
    conversions: int
    roas: float
    vs_prior_period_pct: float


class ChannelPerformance(BaseModel):
    channel: str
    spend: Decimal
    revenue: Decimal
    roas: float
    vs_prior_week_pct: float


class ActivePromotion(BaseModel):
    promotion_id: str
    name: str
    discount_pct: float
    products: list[str]
    status: str  # "scheduled" | "active" | "missed" | "ended"
    scheduled_at: Optional[str] = None


# ── Support ──────────────────────────────────────────────────────────────────

class TicketVolumeSummary(BaseModel):
    date: date
    total_tickets: int
    vs_7day_avg: float
    vs_7day_avg_pct: float
    is_spike: bool


class RefundRateSummary(BaseModel):
    date: date
    refund_rate_pct: float
    return_rate_pct: float
    vs_baseline_pct: float


class ComplaintTheme(BaseModel):
    theme: str
    count: int
    pct_of_total: float
    severity: str  # "low" | "medium" | "high"
    sample_tickets: list[str] = Field(default_factory=list)
