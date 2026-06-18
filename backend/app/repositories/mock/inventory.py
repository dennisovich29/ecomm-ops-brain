from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models.domain import RestockRecommendation, StockLevel, StockoutEvent


PRODUCTS = [
    {"id": "SKU-001", "name": "Wireless Headphones Pro"},
    {"id": "SKU-002", "name": "Running Shoes X2"},
    {"id": "SKU-003", "name": "Yoga Mat Premium"},
    {"id": "SKU-004", "name": "Coffee Grinder 500"},
    {"id": "SKU-005", "name": "Laptop Stand Foldable"},
]

# SKU-001, SKU-002, SKU-003 are out of stock "yesterday"
_OUT_OF_STOCK_SKUS = {"SKU-001", "SKU-002", "SKU-003"}


class MockInventoryRepository:
    async def get_stock_levels(self, product_ids: list[str] | None = None) -> list[StockLevel]:
        products = PRODUCTS if not product_ids else [p for p in PRODUCTS if p["id"] in product_ids]
        levels = []
        for p in products:
            if p["id"] in _OUT_OF_STOCK_SKUS:
                levels.append(StockLevel(
                    product_id=p["id"],
                    product_name=p["name"],
                    current_stock=0,
                    reorder_point=50,
                    days_of_stock=0.0,
                    status="out_of_stock",
                ))
            elif p["id"] == "SKU-004":
                levels.append(StockLevel(
                    product_id=p["id"],
                    product_name=p["name"],
                    current_stock=12,
                    reorder_point=20,
                    days_of_stock=1.5,
                    status="critical",
                ))
            else:
                levels.append(StockLevel(
                    product_id=p["id"],
                    product_name=p["name"],
                    current_stock=250,
                    reorder_point=30,
                    days_of_stock=31.0,
                    status="ok",
                ))
        return levels

    async def get_stockout_events(self, target_date: date) -> list[StockoutEvent]:
        yesterday = date.today() - timedelta(days=1)
        if target_date != yesterday:
            return []
        return [
            StockoutEvent(
                product_id=sku,
                product_name=next(p["name"] for p in PRODUCTS if p["id"] == sku),
                stockout_start=str(target_date) + "T00:00:00",
                stockout_end=None,
                estimated_lost_revenue=Decimal("5200.00"),
            )
            for sku in _OUT_OF_STOCK_SKUS
        ]

    async def get_restock_recommendations(self) -> list[RestockRecommendation]:
        return [
            RestockRecommendation(
                product_id="SKU-001",
                product_name="Wireless Headphones Pro",
                recommended_quantity=500,
                urgency="immediate",
                reason="Out of stock; top revenue contributor.",
            ),
            RestockRecommendation(
                product_id="SKU-002",
                product_name="Running Shoes X2",
                recommended_quantity=300,
                urgency="immediate",
                reason="Out of stock; second-highest seller.",
            ),
            RestockRecommendation(
                product_id="SKU-003",
                product_name="Yoga Mat Premium",
                recommended_quantity=200,
                urgency="immediate",
                reason="Out of stock.",
            ),
        ]

    async def get_views_vs_purchases(self, target_date: date) -> list[dict]:
        yesterday = date.today() - timedelta(days=1)
        if target_date == yesterday:
            return [
                {"product_id": "SKU-001", "views": 1800, "purchases": 0, "lost_conversions": 1800},
                {"product_id": "SKU-002", "views": 1200, "purchases": 0, "lost_conversions": 1200},
                {"product_id": "SKU-003", "views": 900, "purchases": 0, "lost_conversions": 900},
            ]
        return []
