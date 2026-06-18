from __future__ import annotations

from app.graph.state import OpsState


def edge_dispatch_agents(state: OpsState) -> list[str]:
    """Return node names for domains to dispatch — enables parallel dispatch.

    On re-query (reflection_passes > 0), only dispatch to domains flagged in
    gaps_identified so existing findings from other domains are preserved.
    Returns ["format_response"] directly for GENERAL (conversational) queries.
    """
    domain_node_map = {
        "sales": "run_sales_agent",
        "inventory": "run_inventory_agent",
        "marketing": "run_marketing_agent",
        "support": "run_support_agent",
    }

    intent = state.get("intent") or {}
    query_type = intent.get("query_type", "DIAGNOSTIC")

    # Short-circuit: conversational queries skip all agents
    if query_type == "GENERAL":
        return ["format_response"]

    domains = intent.get("domains", [])
    # Don't default to all domains — if no domain is relevant, go straight to format
    if not domains:
        return ["format_response"]

    gaps = state.get("gaps_identified", [])
    if gaps and state.get("reflection_passes", 0) > 0:
        domains = [d for d in domains if d in gaps]

    result = [domain_node_map[d] for d in domains if d in domain_node_map]
    return result if result else ["format_response"]


def edge_after_reflection(state: OpsState) -> str:
    """After reflection: re-query if gaps remain, else proceed to memory retrieval.

    SUMMARY queries skip synthesis entirely — findings are formatted directly.
    """
    query_type = (state.get("intent") or {}).get("query_type", "DIAGNOSTIC")
    if query_type == "SUMMARY":
        return "format_response"
    from app.agents.reflection_agent import should_re_query
    return should_re_query(state)


def edge_after_synthesis(state: OpsState) -> str:
    """After synthesis: propose actions if ACTION/HYBRID, else format response."""
    query_type = (state.get("intent") or {}).get("query_type", "DIAGNOSTIC")
    if query_type in ("ACTION", "HYBRID"):
        return "propose_actions"
    return "format_response"


def edge_after_hitl(state: OpsState) -> str:
    """After HITL checkpoint resumes: execute if actions were approved, else format."""
    return "execute_actions" if state.get("approved_actions") else "format_response"


def edge_after_execution(state: OpsState) -> str:
    """After execution: store incident then format response."""
    return "store_incident"
