from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class TimeRange(TypedDict):
    start: str   # ISO date string
    end: str


class Intent(TypedDict):
    query_type: str          # DIAGNOSTIC | ACTION | MEMORY | SUMMARY | HYBRID
    domains: list[str]       # subsets of [sales, inventory, marketing, support]
    time_range: TimeRange
    entities: list[str]      # product names, campaign IDs, etc.


class OpsState(TypedDict):
    # ── Input ─────────────────────────────────────────
    user_query: str
    session_id: str
    turn_id: str

    # ── Routing ───────────────────────────────────────
    intent: Optional[Intent]
    active_agents: list[str]

    # ── Agent Findings ────────────────────────────────
    sales_findings: Optional[dict]
    inventory_findings: Optional[dict]
    marketing_findings: Optional[dict]
    support_findings: Optional[dict]

    # ── Reflection ────────────────────────────────────
    reflection_notes: list[str]
    confidence_score: float
    gaps_identified: list[str]
    reflection_passes: int

    # ── Memory ────────────────────────────────────────
    similar_incidents: list[dict]
    current_incident_id: Optional[str]

    # ── Actions ───────────────────────────────────────
    proposed_actions: list[dict]
    approved_actions: list[dict]
    executed_actions: list[dict]

    # ── Response ──────────────────────────────────────
    root_cause_analysis: Optional[str]
    recommendations: list[str]
    final_response: Optional[dict]
    # ── Session Context (from prior turn) ─────────────────
    prior_context: Optional[str]
    # ── Conversation ──────────────────────────────────
    messages: Annotated[list, add_messages]
