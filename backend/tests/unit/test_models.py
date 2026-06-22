"""Unit tests for Pydantic models."""
from __future__ import annotations

import uuid
import pytest
from app.models.api import ChatRequest, ApprovalRequest, DeclineRequest
from app.models.actions import ProposedAction, ApprovedAction, ActionResult


# ── ChatRequest ──────────────────────────────────────────────────────────────

def test_chat_request_valid():
    req = ChatRequest(content="Why did sales drop?")
    assert req.content == "Why did sales drop?"
    assert isinstance(req.session_id, str)
    assert len(req.session_id) > 0


def test_chat_request_auto_session_id():
    req1 = ChatRequest(content="hello")
    req2 = ChatRequest(content="hello")
    assert req1.session_id != req2.session_id


def test_chat_request_explicit_session_id():
    sid = str(uuid.uuid4())
    req = ChatRequest(content="hello", session_id=sid)
    assert req.session_id == sid


def test_chat_request_too_short():
    with pytest.raises(Exception):
        ChatRequest(content="")


def test_chat_request_too_long():
    with pytest.raises(Exception):
        ChatRequest(content="x" * 2001)


# ── ApprovalRequest ──────────────────────────────────────────────────────────

def test_approval_request_valid():
    req = ApprovalRequest(
        request_id="req-123",
        approved_action_ids=["action-1", "action-2"],
    )
    assert req.request_id == "req-123"
    assert len(req.approved_action_ids) == 2


def test_approval_request_empty_ids():
    req = ApprovalRequest(request_id="req-123", approved_action_ids=[])
    assert req.approved_action_ids == []


# ── DeclineRequest ───────────────────────────────────────────────────────────

def test_decline_request_valid():
    req = DeclineRequest(request_id="req-456")
    assert req.request_id == "req-456"


# ── ProposedAction ───────────────────────────────────────────────────────────

def test_proposed_action_restock():
    action = ProposedAction(
        action_type="restock_product",
        parameters={"product_id": "SKU-001", "quantity": 500},
        justification="Out of stock",
        impact_estimate="Restores 30% revenue",
        reversible=True,
    )
    assert action.action_type == "restock_product"
    assert action.parameters["product_id"] == "SKU-001"
    assert action.reversible is True


def test_proposed_action_defaults():
    action = ProposedAction(
        action_type="pause_campaign",
        parameters={"campaign_id": "CAMP-001"},
        justification="Poor ROAS",
    )
    assert action.impact_estimate is None
    assert action.reversible is True
    assert isinstance(action.action_id, str)


def test_proposed_action_serializable():
    action = ProposedAction(
        action_type="apply_discount",
        parameters={"product_id": "SKU-002", "discount_pct": 10},
        justification="Drive conversion",
    )
    d = action.model_dump(mode="json")
    assert d["action_type"] == "apply_discount"
    assert isinstance(d["parameters"], dict)


def test_action_result_fields():
    result = ActionResult(
        action_id="act-1",
        action_type="restock_product",
        success=True,
        message="Restocked 500 units",
        executed_at="2026-06-19T00:00:00",
    )
    assert result.success is True
    assert result.message == "Restocked 500 units"

