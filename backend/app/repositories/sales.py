"""PostgreSQL implementation of ISalesRepository."""
from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.db.postgres import get_db_session
from app.models.domain import AnomalyResult, DailyRevenue, ProductSales, RegionalSales


class PostgresSalesRepository:
    async def get_daily_revenue(self, target_date: date) -> DailyRevenue:
        async with get_db_session() as db:
            row = (await db.execute(
                text("SELECT date, revenue, order_count, avg_order_value FROM daily_sales WHERE date = :d"),
                {"d": target_date},
            )).mappings().one_or_none()

        if row is None:
            return DailyRevenue(
                date=target_date, revenue=Decimal("0"), order_count=0,
                avg_order_value=Decimal("0"), vs_prior_day_pct=0.0, vs_prior_week_pct=0.0,
            )

        async with get_db_session() as db:
            prior_day = (await db.execute(
                text("SELECT revenue FROM daily_sales WHERE date = :d"),
                {"d": target_date - timedelta(days=1)},
            )).scalar_one_or_none()
            prior_week = (await db.execute(
                text("SELECT revenue FROM daily_sales WHERE date = :d"),
                {"d": target_date - timedelta(days=7)},
            )).scalar_one_or_none()

        rev = Decimal(str(row["revenue"]))
        vs_day = float((rev - Decimal(str(prior_day))) / Decimal(str(prior_day)) * 100) if prior_day else 0.0
        vs_week = float((rev - Decimal(str(prior_week))) / Decimal(str(prior_week)) * 100) if prior_week else 0.0

        return DailyRevenue(
            date=row["date"],
            revenue=rev,
            order_count=row["order_count"],
            avg_order_value=Decimal(str(row["avg_order_value"])),
            vs_prior_day_pct=round(vs_day, 1),
            vs_prior_week_pct=round(vs_week, 1),
        )

    async def get_product_breakdown(self, target_date: date) -> list[ProductSales]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT pds.product_id, p.name, p.category,
                           pds.units_sold, pds.revenue
                    FROM product_daily_sales pds
                    JOIN products p ON p.id = pds.product_id
                    WHERE pds.date = :d
                    ORDER BY pds.revenue DESC
                """),
                {"d": target_date},
            )).mappings().all()

        if not rows:
            return []

        total = sum(Decimal(str(r["revenue"])) for r in rows) or Decimal("1")
        return [
            ProductSales(
                product_id=r["product_id"],
                product_name=r["name"],
                category=r["category"],
                units_sold=r["units_sold"],
                revenue=Decimal(str(r["revenue"])),
                revenue_contribution_pct=round(float(Decimal(str(r["revenue"])) / total * 100), 1),
            )
            for r in rows
        ]

    async def get_regional_breakdown(self, target_date: date) -> list[RegionalSales]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT rs.region, rs.revenue, rs.order_count,
                           COALESCE(baseline.avg_revenue, rs.revenue) AS baseline_rev
                    FROM regional_sales rs
                    LEFT JOIN (
                        SELECT region, AVG(revenue) AS avg_revenue
                        FROM regional_sales
                        WHERE date BETWEEN :window_start AND :window_end
                        GROUP BY region
                    ) baseline ON baseline.region = rs.region
                    WHERE rs.date = :d
                """),
                {"d": target_date,
                 "window_start": target_date - timedelta(days=30),
                 "window_end": target_date - timedelta(days=1)},
            )).mappings().all()

        return [
            RegionalSales(
                region=r["region"],
                revenue=Decimal(str(r["revenue"])),
                order_count=r["order_count"],
                vs_baseline_pct=round(
                    float((Decimal(str(r["revenue"])) - Decimal(str(r["baseline_rev"]))
                           ) / Decimal(str(r["baseline_rev"])) * 100
                    ) if r["baseline_rev"] else 0.0, 1
                ),
            )
            for r in rows
        ]

    async def detect_anomaly(self, target_date: date, window_days: int = 30) -> AnomalyResult:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT revenue FROM daily_sales
                    WHERE date BETWEEN :start AND :end
                    ORDER BY date
                """),
                {"start": target_date - timedelta(days=window_days),
                 "end": target_date - timedelta(days=1)},
            )).scalars().all()

            current = (await db.execute(
                text("SELECT revenue FROM daily_sales WHERE date = :d"),
                {"d": target_date},
            )).scalar_one_or_none()

        if not rows or current is None:
            return AnomalyResult(is_anomaly=False, z_score=0.0, severity="low", description="Insufficient data.")

        values = [float(r) for r in rows]
        mean = sum(values) / len(values)
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values)) or 1.0
        z = round((float(current) - mean) / std, 2)
        is_anomaly = abs(z) >= 2.0
        severity = "high" if abs(z) >= 2.5 else "medium" if abs(z) >= 2.0 else "low"
        direction = "below" if z < 0 else "above"
        description = (
            f"Revenue is {abs(z)} standard deviations {direction} the {window_days}-day mean."
            if is_anomaly else "Normal."
        )
        return AnomalyResult(is_anomaly=is_anomaly, z_score=z, severity=severity, description=description)

    async def compare_periods(self, target_date: date) -> dict:
        current = await self.get_daily_revenue(target_date)
        prior = await self.get_daily_revenue(target_date - timedelta(days=7))
        return {
            "current": current.model_dump(mode="json"),
            "prior_week_same_day": prior.model_dump(mode="json"),
            "revenue_delta_pct": current.vs_prior_week_pct,
        }
