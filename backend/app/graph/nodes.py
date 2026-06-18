from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import interrupt

from app.agents.intent_router import route_intent
from app.agents.reflection_agent import reflect
from app.agents.sales_agent import get_sales_agent
from app.agents.inventory_agent import get_inventory_agent
from app.agents.marketing_agent import get_marketing_agent
from app.agents.support_agent import get_support_agent
from app.core.llm import get_chat_llm
from app.core.observability import get_callbacks
from app.graph.state import OpsState

logger = logging.getLogger(__name__)


# ── Intent Routing ─────────────────────────────────────────────────────────

async def node_route_intent(state: OpsState) -> dict:
    intent = await route_intent(state["user_query"], state["session_id"])
    result: dict = {
        "intent": intent,
        "active_agents": intent["domains"],
        "turn_id": state.get("turn_id") or str(uuid.uuid4()),
        "messages": [HumanMessage(content=state["user_query"])],
    }
    # On re-query (reflection found gaps), preserve existing findings so only
    # the missing domains are re-run. On a fresh turn, reset everything.
    if not state.get("reflection_passes"):
        result.update({
            "sales_findings": None,
            "inventory_findings": None,
            "marketing_findings": None,
            "support_findings": None,
            "reflection_passes": 0,
            "gaps_identified": [],
            "reflection_notes": [],
            "confidence_score": 0.0,
            "proposed_actions": [],
            "approved_actions": [],
            "executed_actions": [],
        })
    return result


# ── Specialist Agent Nodes ──────────────────────────────────────────────────

def _extract_last_content(messages: list) -> str:
    for m in reversed(messages):
        if hasattr(m, "content") and m.content:
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def _parse_findings(content: str) -> dict:
    """Try to parse JSON from agent output; fall back to raw text."""
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except Exception:
        pass
    return {"raw": content}


async def node_run_sales_agent(state: OpsState) -> dict:
    agent = get_sales_agent()
    callbacks = get_callbacks(state["session_id"], "sales")
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=f"Analyze sales for: {state['user_query']}")]},
        config={"callbacks": callbacks}
    )
    content = _extract_last_content(result.get("messages", []))
    return {"sales_findings": _parse_findings(content)}


async def node_run_inventory_agent(state: OpsState) -> dict:
    agent = get_inventory_agent()
    callbacks = get_callbacks(state["session_id"], "inventory")
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=f"Analyze inventory for: {state['user_query']}")]},
        config={"callbacks": callbacks}
    )
    content = _extract_last_content(result.get("messages", []))
    return {"inventory_findings": _parse_findings(content)}


async def node_run_marketing_agent(state: OpsState) -> dict:
    agent = get_marketing_agent()
    callbacks = get_callbacks(state["session_id"], "marketing")
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=f"Analyze marketing for: {state['user_query']}")]},
        config={"callbacks": callbacks}
    )
    content = _extract_last_content(result.get("messages", []))
    return {"marketing_findings": _parse_findings(content)}


async def node_run_support_agent(state: OpsState) -> dict:
    agent = get_support_agent()
    callbacks = get_callbacks(state["session_id"], "support")
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=f"Analyze customer support signals for: {state['user_query']}")]},
        config={"callbacks": callbacks}
    )
    content = _extract_last_content(result.get("messages", []))
    return {"support_findings": _parse_findings(content)}


# ── Reflection ──────────────────────────────────────────────────────────────

async def node_run_reflection(state: OpsState) -> dict:
    return reflect(state)


# ── Memory Retrieval ────────────────────────────────────────────────────────

async def node_retrieve_memory(state: OpsState) -> dict:
    """Retrieve semantically similar past incidents from Qdrant."""
    try:
        from app.memory.episodic import retrieve_similar_incidents
        query_text = _build_incident_text(state)
        similar = await retrieve_similar_incidents(query_text, top_k=3)
        return {"similar_incidents": similar}
    except Exception:
        return {"similar_incidents": []}


def _build_incident_text(state: OpsState) -> str:
    parts = [state.get("user_query", "")]
    if state.get("sales_findings"):
        parts.append(f"sales: {json.dumps(state['sales_findings'])[:300]}")
    if state.get("inventory_findings"):
        parts.append(f"inventory: {json.dumps(state['inventory_findings'])[:300]}")
    if state.get("marketing_findings"):
        parts.append(f"marketing: {json.dumps(state['marketing_findings'])[:300]}")
    if state.get("support_findings"):
        parts.append(f"support: {json.dumps(state['support_findings'])[:300]}")
    return " | ".join(parts)


# ── Synthesis ───────────────────────────────────────────────────────────────

async def node_synthesize_findings(state: OpsState) -> dict:
    llm = get_chat_llm()
    callbacks = get_callbacks(state["session_id"], "synthesis")

    findings_summary = json.dumps({
        "sales": state.get("sales_findings"),
        "inventory": state.get("inventory_findings"),
        "marketing": state.get("marketing_findings"),
        "support": state.get("support_findings"),
    }, indent=2)

    memory_context = ""
    if state.get("similar_incidents"):
        memory_context = f"\n\nPast similar incidents:\n{json.dumps(state['similar_incidents'], indent=2)[:800]}"

    prior_context = ""
    if state.get("prior_context"):
        prior_context = f"\n\nPrior conversation context:\n{state['prior_context']}"

    prompt = f"""You are answering an e-commerce operations question based on data gathered by specialist agents.

User question: {state['user_query']}

Agent findings:
{findings_summary}
{memory_context}
{prior_context}

Rules for your response:
1. **Answer the question directly in the first line.** 
   - If it's a yes/no question (e.g. "are there issues?", "is X underperforming?") → start with **Yes** or **No**, then one sentence summary.
   - If it's a "what/why/how" question → give a direct 1-sentence answer first.
   - If it's a status/overview question → give a 1-line headline first.
2. Then provide **Supporting Data** — bullet points with specific numbers, product names, dates from the findings. No vague statements.
3. Then provide a short **Explanation** of why this is happening, if relevant.

Do NOT use generic RCA headers like "Root Cause", "Contributing Factors", "Impact Summary".
Use plain section headers that match the question (e.g. "Underperforming Campaigns", "What's Driving This", "What This Means").
Be factual. Only reference data that appears in the findings above. Do not pad or repeat yourself.
Do NOT include a confidence score or confidence line in your response — it is shown separately in the UI."""

    response = await llm.ainvoke(prompt, config={"callbacks": callbacks})
    rca = response.content if hasattr(response, "content") else str(response)

    # Strip any confidence line the LLM may have included anyway
    import re
    rca = re.sub(r'\n?\*{0,2}Confidence[:\s–—]*[\d\.]+%.*', '', rca, flags=re.IGNORECASE).strip()

    return {
        "root_cause_analysis": rca,
        "messages": [AIMessage(content=rca)],
    }


# ── Action Proposal ─────────────────────────────────────────────────────────

async def node_propose_actions(state: OpsState) -> dict:
    from app.agents.action_agent import propose_actions
    actions = await propose_actions(state)
    return {"proposed_actions": actions}


# ── HITL Checkpoint ─────────────────────────────────────────────────────────

async def node_hitl_checkpoint(state: OpsState) -> dict:
    """Pause graph execution for human approval via LangGraph interrupt().

    On first pass: interrupt() serializes state to the checkpointer and the
    graph pauses. The SSE handler detects the interrupt and sends an
    approval_request event to the frontend.

    On resume (POST /actions/approve or /actions/decline): interrupt() returns
    the decision dict sent via Command(resume=...). Approved action IDs are
    matched against the proposed list and stored in approved_actions.
    """
    proposed = state.get("proposed_actions", [])
    if not proposed:
        return {"approved_actions": []}

    decision = interrupt({"proposed_actions": proposed})
    approved_ids = set(decision.get("approved_action_ids", []))
    approved = [a for a in proposed if a.get("action_id") in approved_ids]
    return {"approved_actions": approved}


# ── Execute Actions ──────────────────────────────────────────────────────────

async def node_execute_actions(state: OpsState) -> dict:
    from app.tools.action_tools import execute_action
    results = []
    for action in state.get("approved_actions", []):
        result = await execute_action(action)
        results.append(result)
    return {"executed_actions": results}


# ── Store Incident ───────────────────────────────────────────────────────────

async def node_store_incident(state: OpsState) -> dict:
    try:
        from app.memory.episodic import store_incident
        incident_id = await store_incident(state)
        return {"current_incident_id": incident_id}
    except Exception:
        return {}


# ── Format Final Response ────────────────────────────────────────────────────

async def node_format_response(state: OpsState) -> dict:
    query_type = (state.get("intent") or {}).get("query_type", "DIAGNOSTIC")

    if query_type == "GENERAL":
        response = await _format_general_response(state)
    elif query_type == "SUMMARY":
        response = _format_summary_response(state)
    elif query_type == "MEMORY":
        response = _format_memory_response(state)
    elif query_type in ("ACTION", "HYBRID") and state.get("executed_actions"):
        response = _format_action_response(state)
    else:
        response = _format_diagnostic_response(state)

    return {
        "final_response": response,
        "messages": [AIMessage(content=response.get("summary", ""))],
    }


async def _format_general_response(state: OpsState) -> dict:
    """Use the LLM to answer the specific conversational question with system context."""
    llm = get_chat_llm()
    callbacks = get_callbacks(state["session_id"], "general")

    system_context = """You are OpsCore Brain, an AI assistant for e-commerce operations monitoring and diagnosis.

You have the following specialist agents:
- **Sales Agent** — analyzes revenue, order volume, anomalies, product breakdowns, regional performance
- **Inventory Agent** — tracks stock levels, stockout events, lost conversions, restock recommendations
- **Marketing Agent** — evaluates campaign performance, channel metrics, active promotions
- **Support Agent** — monitors ticket volume, complaint themes, refund/return rates, CSAT

Your tools include:
- Sales: get_daily_revenue, detect_sales_anomaly, compare_sales_periods, get_product_sales_breakdown, get_regional_sales
- Inventory: get_stock_levels, get_stockout_events, get_restock_recommendations, get_views_vs_purchases
- Marketing: get_campaign_metrics, get_channel_performance, get_active_promotions
- Support: get_ticket_volume, get_complaint_themes, get_refund_return_rates, get_csat_scores
- Actions (require human approval): restock_product, apply_discount, pause_campaign, resume_campaign, create_support_ticket

You can run DIAGNOSTIC (root cause analysis), ACTION (propose + execute changes with approval), MEMORY (recall past incidents), or SUMMARY queries.

IMPORTANT: You are answering a conversational or informational question — no agents have been run and no live data has been fetched. 
Do NOT fabricate data, do NOT pretend to run diagnostics, and do NOT make up findings.
Answer the user's question directly based only on what you know about yourself and your capabilities.
Be concise and use markdown formatting."""

    response = await llm.ainvoke(
        [
            {"role": "system", "content": system_context},
            {"role": "user", "content": state.get("user_query", "")},
        ],
        config={"callbacks": callbacks},
    )
    answer = response.content if hasattr(response, "content") else str(response)

    return {
        "type": "general",
        "query": state.get("user_query"),
        "summary": answer,
    }


def _format_diagnostic_response(state: OpsState) -> dict:
    domains = (state.get("intent") or {}).get("domains", [])
    return {
        "type": "diagnostic",
        "query": state.get("user_query"),
        "confidence_score": state.get("confidence_score"),
        "domains_investigated": domains,
        "similar_incidents": state.get("similar_incidents", []),
        # summary contains the full RCA markdown — rendered by the frontend as markdown
        "summary": state.get("root_cause_analysis", "Analysis complete."),
    }


def _format_summary_response(state: OpsState) -> dict:
    """For SUMMARY queries: present raw agent findings directly, no RCA synthesis."""
    domains = (state.get("intent") or {}).get("domains", [])
    findings: dict = {}
    if state.get("inventory_findings"):
        findings["inventory"] = state["inventory_findings"]
    if state.get("sales_findings"):
        findings["sales"] = state["sales_findings"]
    if state.get("marketing_findings"):
        findings["marketing"] = state["marketing_findings"]
    if state.get("support_findings"):
        findings["support"] = state["support_findings"]

    sections = []

    # ── Inventory ─────────────────────────────────────────────────────────
    inv = findings.get("inventory", {})
    if inv:
        inv_lines = []
        if inv.get("stockout_events"):
            inv_lines.append("**Out of Stock**")
            inv_lines.append("| Product | Est. Lost Revenue | Since |")
            inv_lines.append("|---|---|---|")
            for e in inv["stockout_events"]:
                name = e.get("product_name", e.get("product_id", "?"))
                lost = f"${float(e.get('estimated_lost_revenue', 0)):,.2f}" if e.get("estimated_lost_revenue") else "—"
                since = (e.get("stockout_start", "")[:10]) or "—"
                inv_lines.append(f"| {name} | {lost} | {since} |")
            inv_lines.append("")

        if inv.get("low_stock_products"):
            inv_lines.append("**Low Stock**")
            inv_lines.append("| Product | Units Left | Days of Stock | Status |")
            inv_lines.append("|---|---|---|---|")
            for p in inv["low_stock_products"]:
                name = p.get("product_name", p.get("product_id", "?"))
                units = p.get("current_stock", "?")
                days = p.get("days_of_stock", "?")
                status = p.get("status", "").capitalize()
                inv_lines.append(f"| {name} | {units} | {days}d | {status} |")
            inv_lines.append("")

        if inv.get("restock_recommendations"):
            inv_lines.append("**Restock Recommendations**")
            inv_lines.append("| Product | Qty | Urgency |")
            inv_lines.append("|---|---|---|")
            for r in inv["restock_recommendations"]:
                name = r.get("product_name", r.get("product_id", "?"))
                qty = r.get("recommended_quantity", "?")
                urgency = r.get("urgency", "?").capitalize()
                inv_lines.append(f"| {name} | {qty} | {urgency} |")
            inv_lines.append("")

        if inv_lines:
            sections.append("### Inventory\n" + "\n".join(inv_lines))

    # ── Sales ─────────────────────────────────────────────────────────────
    sal = findings.get("sales", {})
    if sal:
        sal_lines = []
        if sal.get("revenue_summary"):
            rev = sal["revenue_summary"]
            revenue = f"${float(rev.get('revenue', 0)):,.2f}"
            orders = rev.get("order_count", "?")
            aov = f"${float(rev.get('avg_order_value', 0)):,.2f}"
            vs_day = rev.get("vs_prior_day_pct", "?")
            vs_week = rev.get("vs_prior_week_pct", "?")
            sal_lines.append("| Metric | Value |")
            sal_lines.append("|---|---|")
            sal_lines.append(f"| Revenue | {revenue} |")
            sal_lines.append(f"| Orders | {orders} |")
            sal_lines.append(f"| Avg Order Value | {aov} |")
            sal_lines.append(f"| vs Prior Day | {vs_day}% |")
            sal_lines.append(f"| vs Prior Week | {vs_week}% |")
            sal_lines.append("")

        if sal.get("anomaly_result"):
            an = sal["anomaly_result"]
            if an.get("is_anomaly"):
                sal_lines.append(f"⚠ **Anomaly detected** — {an.get('description', '')}")
            else:
                sal_lines.append(f"{an.get('description', 'No anomaly detected.')}")

        if sal.get("top_affected_products"):
            sal_lines.append("")
            sal_lines.append("**Top Products**")
            sal_lines.append("| Product | Units | Revenue | Share |")
            sal_lines.append("|---|---|---|---|")
            for p in sal["top_affected_products"][:5]:
                name = p.get("product_name", p.get("product_id", "?"))
                units = p.get("units_sold", "?")
                rev_p = f"${float(p.get('revenue', 0)):,.2f}"
                share = f"{p.get('revenue_contribution_pct', '?')}%"
                sal_lines.append(f"| {name} | {units} | {rev_p} | {share} |")

        if sal_lines:
            sections.append("### Sales\n" + "\n".join(sal_lines))

    # ── Marketing ─────────────────────────────────────────────────────────
    mkt = findings.get("marketing", {})
    if mkt:
        mkt_lines = []
        if mkt.get("campaign_issues"):
            mkt_lines.append("**Campaign Issues**")
            for issue in mkt["campaign_issues"]:
                name = issue.get("campaign_name", issue.get("campaign_id", "?"))
                desc = issue.get("issue", issue.get("description", ""))
                mkt_lines.append(f"- **{name}**: {desc}")
            mkt_lines.append("")
        if mkt.get("promotion_issues"):
            mkt_lines.append("**Promotion Issues**")
            for p in mkt["promotion_issues"]:
                name = p.get("name", p.get("promotion_id", "?"))
                desc = p.get("issue", p.get("description", ""))
                mkt_lines.append(f"- **{name}**: {desc}")


        if mkt_lines:
            sections.append("### Marketing\n" + "\n".join(mkt_lines))

    # ── Support ───────────────────────────────────────────────────────────
    sup = findings.get("support", {})
    if sup:
        sup_lines = []
        if sup.get("ticket_summary"):
            ts = sup["ticket_summary"]
            sup_lines.append("| Metric | Value |")
            sup_lines.append("|---|---|")
            if ts.get("total_tickets") is not None:
                sup_lines.append(f"| Total Tickets | {ts['total_tickets']} |")
            if ts.get("vs_7day_avg_pct") is not None:
                sup_lines.append(f"| vs 7-Day Avg | {ts['vs_7day_avg_pct']}% |")
            if ts.get("refund_rate") is not None:
                sup_lines.append(f"| Refund Rate | {ts['refund_rate']}% |")
            sup_lines.append("")
        if sup.get("top_complaint_themes"):
            sup_lines.append("**Top Complaint Themes**")
            for t in sup["top_complaint_themes"][:3]:
                theme = t.get("theme", "?")
                count = t.get("count", "?")
                pct = t.get("pct_of_total", "?")
                sup_lines.append(f"- {theme} — {count} tickets ({pct}%)")


        if sup_lines:
            sections.append("### Support\n" + "\n".join(sup_lines))

    summary = "\n\n".join(sections) if sections else "No significant findings for the requested domains."

    return {
        "type": "summary",
        "query": state.get("user_query"),
        "confidence_score": state.get("confidence_score"),
        "domains_investigated": domains,
        "findings": findings,
        "summary": summary,
    }


def _format_action_response(state: OpsState) -> dict:
    executed = state.get("executed_actions", [])
    succeeded = [a for a in executed if a.get("success")]
    failed = [a for a in executed if not a.get("success")]
    summary = f"{len(succeeded)} action(s) executed successfully."
    if failed:
        summary += f" {len(failed)} failed."
    return {
        "type": "action_executed",
        "query": state.get("user_query"),
        "executed_actions": executed,
        "summary": summary,
    }


def _format_memory_response(state: OpsState) -> dict:
    incidents = state.get("similar_incidents", [])
    if not incidents:
        summary = "No similar past incidents found in memory."
    else:
        summary = f"Found {len(incidents)} similar past incident(s)."
    return {
        "type": "memory_recall",
        "query": state.get("user_query"),
        "similar_incidents": incidents,
        "summary": summary,
    }
