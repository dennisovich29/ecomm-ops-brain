from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models.domain import ActivePromotion, CampaignMetric, ChannelPerformance


class MockMarketingRepository:
    async def get_campaign_metrics(self, target_date: date) -> list[CampaignMetric]:
        yesterday = date.today() - timedelta(days=1)
        is_bad = target_date == yesterday
        return [
            CampaignMetric(
                campaign_id="CAMP-001",
                campaign_name="Google Shopping — Electronics",
                channel="paid_search",
                status="paused" if is_bad else "active",
                spend=Decimal("0.00") if is_bad else Decimal("850.00"),
                impressions=0 if is_bad else 42000,
                clicks=0 if is_bad else 1260,
                conversions=0 if is_bad else 95,
                roas=0.0 if is_bad else 4.2,
                vs_prior_period_pct=-100.0 if is_bad else 0.0,
            ),
            CampaignMetric(
                campaign_id="CAMP-002",
                campaign_name="Email — Weekly Deals",
                channel="email",
                status="active",
                spend=Decimal("120.00"),
                impressions=18000,
                clicks=540,
                conversions=38,
                roas=3.1,
                vs_prior_period_pct=-5.0,
            ),
        ]

    async def get_channel_performance(self, target_date: date) -> list[ChannelPerformance]:
        yesterday = date.today() - timedelta(days=1)
        is_bad = target_date == yesterday
        return [
            ChannelPerformance(
                channel="paid_search",
                spend=Decimal("0.00") if is_bad else Decimal("850.00"),
                revenue=Decimal("0.00") if is_bad else Decimal("3570.00"),
                roas=0.0 if is_bad else 4.2,
                vs_prior_week_pct=-100.0 if is_bad else 2.1,
            ),
            ChannelPerformance(
                channel="email",
                spend=Decimal("120.00"),
                revenue=Decimal("1180.00"),
                roas=9.8,
                vs_prior_week_pct=-8.0,
            ),
            ChannelPerformance(
                channel="organic",
                spend=Decimal("0.00"),
                revenue=Decimal("5200.00"),
                roas=0.0,
                vs_prior_week_pct=-22.0 if is_bad else 1.0,
            ),
        ]

    async def get_active_promotions(self) -> list[ActivePromotion]:
        return [
            ActivePromotion(
                promotion_id="PROMO-001",
                name="Summer Sale — 15% off Fitness",
                discount_pct=15.0,
                products=["SKU-003"],
                status="missed",
                scheduled_at=str(date.today() - timedelta(days=1)) + "T08:00:00",
            ),
        ]
