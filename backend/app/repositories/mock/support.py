from __future__ import annotations

from datetime import date, timedelta

from app.models.domain import ComplaintTheme, RefundRateSummary, TicketVolumeSummary


class MockSupportRepository:
    async def get_ticket_volume(self, target_date: date) -> TicketVolumeSummary:
        yesterday = date.today() - timedelta(days=1)
        is_bad = target_date == yesterday
        baseline = 48
        count = int(baseline * 2.3) if is_bad else baseline
        return TicketVolumeSummary(
            date=target_date,
            total_tickets=count,
            vs_7day_avg=float(count - baseline),
            vs_7day_avg_pct=((count - baseline) / baseline) * 100,
            is_spike=is_bad,
        )

    async def get_refund_rates(self, target_date: date) -> RefundRateSummary:
        yesterday = date.today() - timedelta(days=1)
        is_bad = target_date == yesterday
        return RefundRateSummary(
            date=target_date,
            refund_rate_pct=6.2 if is_bad else 2.1,
            return_rate_pct=4.8 if is_bad else 1.9,
            vs_baseline_pct=195.0 if is_bad else 0.0,
        )

    async def get_complaint_themes(self, target_date: date) -> list[ComplaintTheme]:
        yesterday = date.today() - timedelta(days=1)
        if target_date == yesterday:
            return [
                ComplaintTheme(
                    theme="Out of stock / can't purchase",
                    count=62,
                    pct_of_total=55.4,
                    severity="high",
                    sample_tickets=[
                        "Item shows out of stock, been trying to buy for 2 hours",
                        "Wireless Headphones Pro unavailable — where is stock?",
                    ],
                ),
                ComplaintTheme(
                    theme="Order delayed / shipping issue",
                    count=18,
                    pct_of_total=16.1,
                    severity="medium",
                    sample_tickets=["Order from 3 days ago still pending"],
                ),
                ComplaintTheme(
                    theme="Refund request",
                    count=12,
                    pct_of_total=10.7,
                    severity="medium",
                    sample_tickets=[],
                ),
            ]
        return [
            ComplaintTheme(
                theme="General inquiry",
                count=20,
                pct_of_total=41.7,
                severity="low",
                sample_tickets=[],
            ),
        ]
