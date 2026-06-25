from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, Date, DateTime, Float, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))


class Inventory(Base):
    __tablename__ = "inventory"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    stock_level: Mapped[int | None] = mapped_column(Integer)
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("50"))


class DailySales(Base):
    __tablename__ = "daily_sales"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    order_count: Mapped[int | None] = mapped_column(Integer)
    avg_order_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))


class ProductDailySales(Base):
    __tablename__ = "product_daily_sales"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))


class RegionalSales(Base):
    __tablename__ = "regional_sales"

    region: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(16))
    daily_budget: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))


class CampaignDailyMetrics(Base):
    __tablename__ = "campaign_daily_metrics"

    campaign_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default=text("0"))
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))


class ChannelDailyPerformance(Base):
    __tablename__ = "channel_daily_performance"

    channel: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default=text("0"))
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))
    products: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default=text("'{}'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'scheduled'"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductViews(Base):
    __tablename__ = "product_views"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    views: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    category: Mapped[str | None] = mapped_column(String(64))
    sentiment: Mapped[str | None] = mapped_column(String(16))
    resolved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
