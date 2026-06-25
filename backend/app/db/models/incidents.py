from __future__ import annotations

from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Float, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    query: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text)
    domains: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    confidence: Mapped[float | None] = mapped_column(Float)
    embedding_id: Mapped[str | None] = mapped_column(String(128))
    resolved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class IncidentAction(Base):
    __tablename__ = "incident_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    incident_id: Mapped[str | None] = mapped_column(String(36))
    action_type: Mapped[str | None] = mapped_column(String(64))
    parameters: Mapped[str | None] = mapped_column(Text)
    approved: Mapped[bool | None] = mapped_column(Boolean)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(Text)
