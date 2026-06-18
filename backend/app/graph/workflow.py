from __future__ import annotations

from langgraph.graph import StateGraph, END

from app.graph.state import OpsState
from app.graph.nodes import (
    node_route_intent,
    node_run_sales_agent,
    node_run_inventory_agent,
    node_run_marketing_agent,
    node_run_support_agent,
    node_run_reflection,
    node_retrieve_memory,
    node_synthesize_findings,
    node_propose_actions,
    node_hitl_checkpoint,
    node_execute_actions,
    node_store_incident,
    node_format_response,
)
from app.graph.edges import (
    edge_dispatch_agents,
    edge_after_reflection,
    edge_after_synthesis,
    edge_after_hitl,
    edge_after_execution,
)


def build_graph() -> StateGraph:
    builder = StateGraph(OpsState)

    # ── Nodes ─────────────────────────────────────────────────────────────
    builder.add_node("route_intent", node_route_intent)
    builder.add_node("run_sales_agent", node_run_sales_agent)
    builder.add_node("run_inventory_agent", node_run_inventory_agent)
    builder.add_node("run_marketing_agent", node_run_marketing_agent)
    builder.add_node("run_support_agent", node_run_support_agent)
    builder.add_node("run_reflection", node_run_reflection)
    builder.add_node("retrieve_memory", node_retrieve_memory)
    builder.add_node("synthesize_findings", node_synthesize_findings)
    builder.add_node("propose_actions", node_propose_actions)
    builder.add_node("hitl_checkpoint", node_hitl_checkpoint)
    builder.add_node("execute_actions", node_execute_actions)
    builder.add_node("store_incident", node_store_incident)
    builder.add_node("format_response", node_format_response)

    # ── Entry ──────────────────────────────────────────────────────────────
    builder.set_entry_point("route_intent")

    # ── Parallel dispatch to specialist agents ─────────────────────────────
    builder.add_conditional_edges(
        "route_intent",
        edge_dispatch_agents,
        {
            "run_sales_agent": "run_sales_agent",
            "run_inventory_agent": "run_inventory_agent",
            "run_marketing_agent": "run_marketing_agent",
            "run_support_agent": "run_support_agent",
            "format_response": "format_response",
        },
    )

    # ── All agents converge at reflection ──────────────────────────────────
    for agent_node in [
        "run_sales_agent",
        "run_inventory_agent",
        "run_marketing_agent",
        "run_support_agent",
    ]:
        builder.add_edge(agent_node, "run_reflection")

    # ── Reflection → re-query or synthesize ───────────────────────────────
    builder.add_conditional_edges(
        "run_reflection",
        edge_after_reflection,
        {
            "re_query": "route_intent",
            "synthesize": "retrieve_memory",
            "format_response": "format_response",
        },
    )

    # ── Memory → synthesis ─────────────────────────────────────────────────
    builder.add_edge("retrieve_memory", "synthesize_findings")

    # ── Synthesis → action or response ────────────────────────────────────
    builder.add_conditional_edges(
        "synthesize_findings",
        edge_after_synthesis,
        {
            "propose_actions": "propose_actions",
            "format_response": "format_response",
        },
    )

    # ── Actions → HITL ────────────────────────────────────────────────────
    builder.add_edge("propose_actions", "hitl_checkpoint")

    # ── HITL → execute or format ───────────────────────────────────────────
    builder.add_conditional_edges(
        "hitl_checkpoint",
        edge_after_hitl,
        {
            "execute_actions": "execute_actions",
            "format_response": "format_response",
        },
    )

    # ── Execution → store → format ────────────────────────────────────────
    builder.add_edge("execute_actions", "store_incident")
    builder.add_edge("store_incident", "format_response")

    # ── Final response → END ──────────────────────────────────────────────
    builder.add_edge("format_response", END)

    return builder


_compiled_graph = None


def init_compiled_graph(checkpointer) -> None:
    global _compiled_graph
    _compiled_graph = build_graph().compile(checkpointer=checkpointer)


def get_compiled_graph():
    if _compiled_graph is None:
        raise RuntimeError("Graph not initialized — call init_compiled_graph() at startup")
    return _compiled_graph
