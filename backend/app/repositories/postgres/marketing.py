"""PostgreSQL implementation of IMarketingRepository."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.db.postgres import get_db_session
from app.models.domain import ActivePromotion, CampaignMetric, ChannelPerformance


class PostgresMarketingRepository:
    async def get_campaign_metrics(self, target_date: date) -> list[CampaignMetric]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT c.id, c.name, c.channel, c.status,
                           COALESCE(m.spend, 0)       AS spend,
                           COALESCE(m.impressions, 0) AS impressions,
                           COALESCE(m.clicks, 0)      AS clicks,
                           COALESCE(m.conversions, 0) AS conversions,
                           COALESCE(m.revenue, 0)     AS revenue,
                           COALESCE(pw.spend, 0)      AS prior_spend
                    FROM campaigns c
                    LEFT JOIN campaign_daily_metrics m
                           ON m.campaign_id = c.id AND m.date = :d
                    LEFT JOIN campaign_daily_metrics pw
                           ON pw.campaign_id = c.id AND pw.date = :pw
                """),
                {"d": target_date, "pw": target_date - timedelta(days=7)},
            )).mappings().all()

        result = []
        for r in rows:
            spend = float(r["spend"])
            revenue = float(r["revenue"])
            roas = round(revenue / spend, 2) if spend > 0 else 0.0
            prior = float(r["prior_spend"])
            vs_prior = round((spend - prior) / prior * 100, 1) if prior > 0 else (-100.0 if spend == 0 else 0.0)
            result.append(CampaignMetric(
                campaign_id=r["id"],
                campaign_name=r["name"],
                channel=r["channel"],
                status=r["status"],
                spend=Decimal(str(r["spend"])),
                impressions=r["impressions"],
                clicks=r["clicks"],
                conversions=r["conversions"],
                roas=roas,
                vs_prior_period_pct=vs_prior,
            ))
        return result

    async def get_channel_performance(self, target_date: date) -> list[ChannelPerformance]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT c.channel, c.spend, c.revenue,
                           COALESCE(pw.revenue, c.revenue) AS prior_revenue
                    FROM channel_daily_performance c
                    LEFT JOIN channel_daily_performance pw
                           ON pw.channel = c.channel AND pw.date = :pw
                    WHERE c.date = :d
                """),
                {"d": target_date, "pw": target_date - timedelta(days=7)},
            )).mappings().all()

        result = []
        for r in rows:
            spend = Decimal(str(r["spend"]))
            revenue = Decimal(str(r["revenue"]))
            prior_rev = float(r["prior_revenue"]) or 1.0
            roas = round(float(revenue) / float(spend), 2) if spend > 0 else 0.0
            vs_week = round((float(revenue) - prior_rev) / prior_rev * 100, 1)
            result.append(ChannelPerformance(
                channel=r["channel"],
                spend=spend,
                revenue=revenue,
                roas=roas,
                vs_prior_week_pct=vs_week,
            ))
        return result

    async def get_active_promotions(self) -> list[ActivePromotion]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("SELECT id, name, discount_pct, products, status, scheduled_at FROM promotions")
            )).mappings().all()

        return [
            ActivePromotion(
                promotion_id=r["id"],
                name=r["name"],
                discount_pct=float(r["discount_pct"]),
                products=list(r["products"]) if r["products"] else [],
                status=r["status"],
                scheduled_at=str(r["scheduled_at"]) if r["scheduled_at"] else None,
            )
            for r in rows
        ]
