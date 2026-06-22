from __future__ import annotations

from langchain.agents import create_agent

from app.agents.middleware import agent_middleware
from app.core.llm import get_chat_llm
from app.tools.inventory_tools import INVENTORY_TOOLS

_SYSTEM = """You are the Inventory Analysis Agent for an e-commerce operations system.

Your job: Identify stock availability issues and their impact on sales.

Always:
1. Call get_stockout_events to find products that ran out of stock
2. Call get_stock_levels for the full picture including near-stockout items
3. Call get_views_vs_purchases to quantify lost conversions from stockouts
4. Call get_restock_recommendations if action is warranted

Summarize findings as structured JSON with keys:
  stockout_events, low_stock_products, lost_conversions_estimate, restock_recommendations, conclusion
"""


def get_inventory_agent():
    llm = get_chat_llm()
    return create_agent(
        model=llm,
        tools=INVENTORY_TOOLS,
        system_prompt=_SYSTEM,
        middleware=agent_middleware(llm),
    )
