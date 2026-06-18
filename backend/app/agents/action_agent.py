from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import text

from app.core.llm import get_chat_llm
from app.db.postgres import get_db_session
from app.graph.state import OpsState
from app.models.actions import ProposedAction

_SYSTEM = """You are the Action Agent for an e-commerce operations system.

Based on the investigation findings, propose concrete, parameterized corrective actions.

IMPORTANT — use ONLY these exact IDs from the live database:
  Products:  {product_ids}
  Campaigns: {campaign_ids}

Do NOT invent product or campaign IDs. If a campaign action is needed, use only the IDs listed above.

For each action:
1. Choose one action_type from: restock_product, apply_discount, pause_campaign, resume_campaign, create_support_ticket
2. Provide specific parameters (product_id, quantity, discount_pct, campaign_id, etc.)
3. Write a clear justification referencing the evidence
4. Estimate impact if known

Return a JSON array of action objects. Example:
[
  {{
    "action_type": "restock_product",
    "parameters": {{"product_id": "SKU-001", "quantity": 500}},
    "justification": "SKU-001 was out of stock all of yesterday causing 1800 lost views.",
    "impact_estimate": "Restores ~30% of lost daily revenue",
    "reversible": true
  }}
]

Only propose actions that are directly supported by the evidence. Do not invent problems."""


async def _get_valid_ids() -> tuple[list[str], list[str]]:
    """Fetch valid product and campaign IDs from DB for grounding."""
    try:
        async with get_db_session() as db:
            p_rows = await db.execute(text("SELECT id FROM products ORDER BY id"))
            c_rows = await db.execute(text("SELECT id, name, status FROM campaigns ORDER BY id"))
            product_ids = [r[0] for r in p_rows.fetchall()]
            campaign_ids = [f"{r[0]} ({r[1]}, {r[2]})" for r in c_rows.fetchall()]
        return product_ids, campaign_ids
    except Exception:
        return [], []


async def propose_actions(state: OpsState) -> list[dict]:
    llm = get_chat_llm()

    product_ids, campaign_ids = await _get_valid_ids()

    findings_summary = json.dumps({
        "sales": state.get("sales_findings"),
        "inventory": state.get("inventory_findings"),
        "marketing": state.get("marketing_findings"),
        "support": state.get("support_findings"),
        "root_cause": state.get("root_cause_analysis"),
    }, indent=2)[:2000]

    system_prompt = _SYSTEM.format(
        product_ids=product_ids or ["(none loaded)"],
        campaign_ids=campaign_ids or ["(none loaded)"],
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "User request: {query}\n\nFindings:\n{findings}"),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({
        "query": state.get("user_query", ""),
        "findings": findings_summary,
    })

    content = response.content if hasattr(response, "content") else str(response)

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
