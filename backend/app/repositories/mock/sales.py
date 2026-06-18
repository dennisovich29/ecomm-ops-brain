from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import statistics

from app.models.domain import (
    AnomalyResult,
    DailyRevenue,
    ProductSales,
    RegionalSales,
)

# ---------------------------------------------------------------------------
# Deterministic seed scenario:
#   - "Yesterday" (date.today() - 1) is always a bad day:
#     35% revenue drop, driven by 3 top-SKU stockouts + campaign pause
# ---------------------------------------------------------------------------

_BASELINE_REVENUE = Decimal("48500.00")
_BASELINE_ORDERS = 320

PRODUCTS = [
    {"id": "SKU-001", "name": "Wireless Headphones Pro", "category": "Electronics"},
    {"id": "SKU-002", "name": "Running Shoes X2", "category": "Footwear"},
    {"id": "SKU-003", "name": "Yoga Mat Premium", "category": "Fitness"},
    {"id": "SKU-004", "name": "Coffee Grinder 500", "category": "Kitchen"},
    {"id": "SKU-005", "name": "Laptop Stand Foldable", "category": "Accessories"},
]


def _get_revenue_for_date(d: date) -> Decimal:
    yesterday = date.today() - timedelta(days=1)
    if d == yesterday:
        return (_BASELINE_REVENUE * Decimal("0.65")).quantize(Decimal("0.01"))
    return _BASELINE_REVENUE


def _get_orders_for_date(d: date) -> int:
    yesterday = date.today() - timedelta(days=1)
    return int(_BASELINE_ORDERS * 0.72) if d == yesterday else _BASELINE_ORDERS


class MockSalesRepository:
    async def get_daily_revenue(self, target_date: date) -> DailyRevenue:
        revenue = _get_revenue_for_date(target_date)
        orders = _get_orders_for_date(target_date)
        prior = _get_revenue_for_date(target_date - timedelta(days=1))
        prior_week = _get_revenue_for_date(target_date - timedelta(days=7))
        return DailyRevenue(
            date=target_date,
            revenue=revenue,
            order_count=orders,
            avg_order_value=(revenue / orders).quantize(Decimal("0.01")),
            vs_prior_day_pct=float((revenue - prior) / prior * 100),
            vs_prior_week_pct=float((revenue - prior_week) / prior_week * 100),
        )

    async def get_product_breakdown(self, target_date: date) -> list[ProductSales]:
        yesterday = date.today() - timedelta(days=1)
        is_bad_day = target_date == yesterday
        total_rev = _get_revenue_for_date(target_date)
        result = []
        shares = [0.30, 0.25, 0.20, 0.15, 0.10] if not is_bad_day else [0.05, 0.05, 0.05, 0.45, 0.40]
        for p, share in zip(PRODUCTS, shares):
            rev = (total_rev * Decimal(str(share))).quantize(Decimal("0.01"))
            result.append(ProductSales(
                product_id=p["id"],
                product_name=p["name"],
                category=p["category"],
                units_sold=int(share * _get_orders_for_date(target_date)),
                revenue=rev,
                revenue_contribution_pct=share * 100,
            ))
        return result

    async def get_regional_breakdown(self, target_date: date) -> list[RegionalSales]:
        yesterday = date.today() - timedelta(days=1)
        is_bad = target_date == yesterday
        regions = [
            ("North America", 0.50),
            ("Europe", 0.30),
            ("Asia Pacific", 0.15),
            ("Rest of World", 0.05),
        ]
        total = _get_revenue_for_date(target_date)
        return [
            RegionalSales(
                region=r,
                revenue=(total * Decimal(str(s))).quantize(Decimal("0.01")),
                order_count=int(_get_orders_for_date(target_date) * s),
                vs_baseline_pct=-35.0 if is_bad else 0.0,
            )
            for r, s in regions
        ]

    async def detect_anomaly(self, target_date: date, window_days: int = 30) -> AnomalyResult:
        yesterday = date.today() - timedelta(days=1)
        if target_date == yesterday:
            return AnomalyResult(
                is_anomaly=True,
                z_score=-2.8,
                severity="high",
                description="Revenue is 2.8 standard deviations below the 30-day mean.",
            )
        return AnomalyResult(is_anomaly=False, z_score=0.1, severity="low", description="Normal.")

    async def compare_periods(self, target_date: date) -> dict:
        rev = await self.get_daily_revenue(target_date)
        prior = await self.get_daily_revenue(target_date - timedelta(days=7))
        return {
            "current": rev.model_dump(),
            "prior_week_same_day": prior.model_dump(),
            "revenue_delta_pct": rev.vs_prior_week_pct,
        }
