"""PostgreSQL implementation of ISupportRepository."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

from app.db.postgres import get_db_session
from app.models.domain import ComplaintTheme, RefundRateSummary, TicketVolumeSummary


class PostgresSupportRepository:
    async def get_ticket_volume(self, target_date: date) -> TicketVolumeSummary:
        async with get_db_session() as db:
            today_count = (await db.execute(
                text("""
                    SELECT COUNT(*) FROM support_tickets
                    WHERE created_at::date = :d
                """),
                {"d": target_date},
            )).scalar_one()

            avg_row = (await db.execute(
                text("""
                    SELECT AVG(daily_count) FROM (
                        SELECT created_at::date AS d, COUNT(*) AS daily_count
                        FROM support_tickets
                        WHERE created_at::date BETWEEN :start AND :end
                        GROUP BY d
                    ) sub
                """),
                {"start": target_date - timedelta(days=7), "end": target_date - timedelta(days=1)},
            )).scalar_one_or_none()

        avg = float(avg_row) if avg_row else float(today_count) or 1.0
        vs = float(today_count) - avg
        vs_pct = round(vs / avg * 100, 1)
        return TicketVolumeSummary(
            date=target_date,
            total_tickets=today_count,
            vs_7day_avg=round(vs, 1),
            vs_7day_avg_pct=vs_pct,
            is_spike=vs_pct > 50,
        )

    async def get_refund_rates(self, target_date: date) -> RefundRateSummary:
        async with get_db_session() as db:
            total = (await db.execute(
                text("SELECT COUNT(*) FROM support_tickets WHERE created_at::date = :d"),
                {"d": target_date},
            )).scalar_one() or 1

            refunds = (await db.execute(
                text("""
                    SELECT COUNT(*) FROM support_tickets
                    WHERE created_at::date = :d
                      AND LOWER(category) LIKE '%refund%'
                """),
                {"d": target_date},
            )).scalar_one()

            returns = (await db.execute(
                text("""
                    SELECT COUNT(*) FROM support_tickets
                    WHERE created_at::date = :d
                      AND LOWER(category) LIKE '%return%'
                """),
                {"d": target_date},
            )).scalar_one()

            baseline_refund = (await db.execute(
                text("""
                    SELECT AVG(daily_refunds::float / NULLIF(daily_total, 0) * 100)
                    FROM (
                        SELECT
                            created_at::date AS d,
                            COUNT(*) FILTER (WHERE LOWER(category) LIKE '%refund%') AS daily_refunds,
                            COUNT(*) AS daily_total
                        FROM support_tickets
                        WHERE created_at::date BETWEEN :start AND :end
                        GROUP BY d
                    ) sub
                """),
                {"start": target_date - timedelta(days=30), "end": target_date - timedelta(days=1)},
            )).scalar_one_or_none()

        refund_pct = round(refunds / total * 100, 1)
        return_pct = round(returns / total * 100, 1)
        baseline = float(baseline_refund) if baseline_refund else refund_pct or 1.0
        vs_baseline = round((refund_pct - baseline) / baseline * 100, 1) if baseline > 0 else 0.0
        return RefundRateSummary(
            date=target_date,
            refund_rate_pct=refund_pct,
            return_rate_pct=return_pct,
            vs_baseline_pct=vs_baseline,
        )

    async def get_complaint_themes(self, target_date: date) -> list[ComplaintTheme]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT category, COUNT(*) AS cnt
                    FROM support_tickets
                    WHERE created_at::date = :d
                    GROUP BY category
                    ORDER BY cnt DESC
                    LIMIT 10
                """),
                {"d": target_date},
            )).mappings().all()

        if not rows:
            return []

        total = sum(r["cnt"] for r in rows) or 1
        themes = []
        for r in rows:
            cnt = r["cnt"]
            pct = round(cnt / total * 100, 1)
            severity = "high" if pct > 40 else "medium" if pct > 20 else "low"
            themes.append(ComplaintTheme(
                theme=r["category"],
                count=cnt,
                pct_of_total=pct,
                severity=severity,
                sample_tickets=[],
            ))
        return themes
