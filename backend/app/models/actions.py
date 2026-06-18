from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
import uuid


class ProposedAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str  # "restock_product" | "apply_discount" | "pause_campaign" | etc.
    parameters: dict
    justification: str
    impact_estimate: Optional[str] = None
    reversible: bool = True


class ApprovedAction(BaseModel):
    action_id: str
    action_type: str
    parameters: dict
    approved_at: str


class ActionResult(BaseModel):
    action_id: str
    action_type: str
    success: bool
    message: str
    executed_at: str
