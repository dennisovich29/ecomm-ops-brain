from __future__ import annotations

import json

from langchain.messages import HumanMessage, SystemMessage
from sqlalchemy import text

from app.core.llm import get_chat_llm
from app.db.postgres import get_db_session
from app.graph.state import OpsState
from app.models.actions import ProposedAction

_SYSTEM_TEMPLATE = """You are the Action Agent for an e-commerce operations system.

Based on the investigation findings, propose concrete, parameterized corrective actions.

━━ VALID IDs — use ONLY these, never invent your own ━━
Products (use exact string as "product_id"):
  {product_ids}

Campaigns (ID — Name — Current Status):
{campaign_info}

━━ CAMPAIGN ACTION RULES ━━
• The "campaign_id" parameter value MUST be the bare ID only — e.g. "CAMP-001".
  NEVER include the name, status, or any extra text in the campaign_id value.
• Status "paused"  → the campaign is already stopped → use "resume_campaign" to reactivate it
• Status "active"  → the campaign is running     → use "pause_campaign" to stop it

━━ SUPPORT TICKET PARAMETER KEYS ━━
Use exactly: "issue_type" (one of: stockout, revenue_drop, campaign_underperformance,
regional_drop, customer_complaint, other) and "description" (short problem statement).

━━ ACTION RULES ━━
1. Choose action_type from: restock_product | apply_discount | pause_campaign | resume_campaign | create_support_ticket
2. Parameters must use ONLY bare IDs from the lists above
3. Write a justification referencing the evidence
4. Estimate impact if known; set "reversible" true/false

Return a JSON array. Examples:
[
  {
    "action_type": "restock_product",
    "parameters": {"product_id": "SKU-001", "quantity": 500},
    "justification": "SKU-001 out of stock caused 1800 lost views yesterday.",
    "impact_estimate": "Restores ~30% of lost daily revenue",
    "reversible": true
  },
  {
    "action_type": "resume_campaign",
    "parameters": {"campaign_id": "CAMP-001"},
    "justification": "CAMP-001 is paused; Electronics needs traffic.",
    "impact_estimate": "Could restore ~10% of lost traffic",
    "reversible": true
  },
  {
    "action_type": "create_support_ticket",
    "parameters": {"issue_type": "regional_drop", "description": "North America revenue down 37.6% vs baseline."},
    "justification": "Regional anomaly needs manual investigation.",
    "impact_estimate": "Unknown until root cause identified",
    "reversible": true
  }
]

Only propose actions directly supported by the evidence. Do not invent problems."""


async def _get_valid_ids() -> tuple[list[str], str]:
    """Fetch valid product and campaign IDs from DB for grounding."""
    try:
        async with get_db_session() as db:
            p_rows = await db.execute(text("SELECT id FROM products ORDER BY id"))
            c_rows = await db.execute(text("SELECT id, name, status FROM campaigns ORDER BY id"))
            product_ids = [r[0] for r in p_rows.fetchall()]
            # Bare IDs kept separate from display context so the LLM never copies the label
            campaign_info = "\n".join(
                f"  {r[0]} — {r[1]} — status: {r[2]}" for r in c_rows.fetchall()
            ) or "  (none)"
        return product_ids, campaign_info
    except Exception:
        return [], "  (unavailable)"


async def propose_actions(state: OpsState) -> list[dict]:
    llm = get_chat_llm()

    product_ids, campaign_info = await _get_valid_ids()

    findings_summary = json.dumps({
        "sales": state.get("sales_findings"),
        "inventory": state.get("inventory_findings"),
        "marketing": state.get("marketing_findings"),
        "support": state.get("support_findings"),
        "root_cause": state.get("root_cause_analysis"),
    }, indent=2)[:2000]

    system_content = (
        _SYSTEM_TEMPLATE
        .replace("{product_ids}", str(product_ids or ["(none loaded)"]))
        .replace("{campaign_info}", campaign_info)
    )
    human_content = (
        f"User request: {state.get('user_query', '')}\n\n"
        f"Findings:\n{findings_summary}"
    )

    response = await llm.ainvoke([
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ])

    content = response.text if hasattr(response, "text") else str(response.content)

    # Parse JSON array from response
    try:
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end > start:
            raw_actions = json.loads(content[start:end])
            return [
                ProposedAction(**a).model_dump(mode="json")
                for a in raw_actions
                if isinstance(a, dict)
            ]
    except Exception:
        pass

    return []
