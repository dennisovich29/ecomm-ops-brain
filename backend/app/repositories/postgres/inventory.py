"""PostgreSQL implementation of IInventoryRepository."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import text

from app.db.postgres import get_db_session
from app.models.domain import RestockRecommendation, StockLevel, StockoutEvent

# Daily sales rate assumed per unit for lost-revenue estimation
_AVG_UNIT_PRICE = {"SKU-001": 89.99, "SKU-002": 74.99, "SKU-003": 49.99,
                   "SKU-004": 39.99, "SKU-005": 34.99}
_AVG_DAILY_UNITS = {"SKU-001": 96, "SKU-002": 80, "SKU-003": 64,
                    "SKU-004": 48, "SKU-005": 32}


class PostgresInventoryRepository:
    async def get_stock_levels(self, product_ids: list[str] | None = None) -> list[StockLevel]:
        query = """
            SELECT i.product_id, p.name, i.stock_level,
                   COALESCE(i.reorder_point, 50) AS reorder_point
            FROM inventory i
            JOIN products p ON p.id = i.product_id
            WHERE i.date = CURRENT_DATE
        """
        params: dict = {}
        if product_ids:
            query += " AND i.product_id = ANY(:ids)"
            params["ids"] = product_ids

        async with get_db_session() as db:
            rows = (await db.execute(text(query), params)).mappings().all()

        result = []
        for r in rows:
            stock = r["stock_level"]
            reorder = r["reorder_point"]
            avg_daily = _AVG_DAILY_UNITS.get(r["product_id"], 50)
            days = round(stock / avg_daily, 1) if avg_daily > 0 else 0.0
            if stock == 0:
                status = "out_of_stock"
            elif stock < reorder:
                status = "critical" if stock < reorder * 0.5 else "low"
            else:
                status = "ok"
            result.append(StockLevel(
                product_id=r["product_id"],
                product_name=r["name"],
                current_stock=stock,
                reorder_point=reorder,
                days_of_stock=days,
                status=status,
            ))
        return result

    async def get_stockout_events(self, target_date: date) -> list[StockoutEvent]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT i.product_id, p.name, i.date
                    FROM inventory i
                    JOIN products p ON p.id = i.product_id
                    WHERE i.date = :d AND i.stock_level = 0
                """),
                {"d": target_date},
            )).mappings().all()

        return [
            StockoutEvent(
                product_id=r["product_id"],
                product_name=r["name"],
                stockout_start=str(r["date"]) + "T00:00:00",
                stockout_end=None,
                estimated_lost_revenue=Decimal(str(round(
                    _AVG_UNIT_PRICE.get(r["product_id"], 50.0) *
                    _AVG_DAILY_UNITS.get(r["product_id"], 50), 2
                ))),
            )
            for r in rows
        ]

    async def get_restock_recommendations(self) -> list[RestockRecommendation]:
        levels = await self.get_stock_levels()
        recs = []
        for sl in levels:
            if sl.status in ("out_of_stock", "critical", "low"):
                base = _AVG_DAILY_UNITS.get(sl.product_id, 50)
                qty = base * 5 if sl.status == "out_of_stock" else base * 2
                urgency = "immediate" if sl.status == "out_of_stock" else (
                    "soon" if sl.status == "critical" else "planned"
                )
                reason = (
                    f"Out of stock; immediate replenishment needed."
                    if sl.status == "out_of_stock"
                    else f"Only {sl.days_of_stock:.1f} days of stock remaining (reorder point: {sl.reorder_point})."
                )
                recs.append(RestockRecommendation(
                    product_id=sl.product_id,
                    product_name=sl.product_name,
                    recommended_quantity=qty,
                    urgency=urgency,
                    reason=reason,
                ))
        return recs

    async def get_views_vs_purchases(self, target_date: date) -> list[dict]:
        async with get_db_session() as db:
            rows = (await db.execute(
                text("""
                    SELECT pv.product_id, p.name,
                           pv.views,
                           COALESCE(pds.units_sold, 0) AS purchases
                    FROM product_views pv
                    JOIN products p ON p.id = pv.product_id
                    LEFT JOIN product_daily_sales pds
                           ON pds.product_id = pv.product_id AND pds.date = pv.date
                    WHERE pv.date = :d
                    ORDER BY pv.views DESC
                """),
                {"d": target_date},
            )).mappings().all()

        return [
            {
                "product_id": r["product_id"],
                "product_name": r["name"],
                "views": r["views"],
                "purchases": r["purchases"],
                "lost_conversions": max(0, r["views"] - r["purchases"]),
            }
            for r in rows
        ]
