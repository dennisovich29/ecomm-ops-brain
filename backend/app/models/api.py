from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
import uuid


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ChatResponse(BaseModel):
    session_id: str
    turn_id: str
    response: dict  # structured final response


class IncidentSummary(BaseModel):
    id: str
    created_at: str
    query: str
    root_cause: Optional[str]
    domains: list[str]
    confidence: Optional[float]
    resolved: bool


class ApprovalRequest(BaseModel):
    request_id: str
    approved_action_ids: list[str]


class DeclineRequest(BaseModel):
    request_id: str
