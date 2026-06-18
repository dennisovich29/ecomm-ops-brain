from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from app.core.llm import get_chat_llm
from app.tools.sales_tools import SALES_TOOLS

_SYSTEM = """You are the Sales Analysis Agent for an e-commerce operations system.

Your job: Investigate sales performance data to identify what happened, when, and how severe it is.

Always:
1. Call get_daily_revenue to get headline numbers
2. Call detect_sales_anomaly to confirm if the drop is statistically significant
3. Call compare_sales_periods to understand trend vs prior periods
4. Call get_product_sales_breakdown to identify which products drove the change
5. Call get_regional_sales if regional data is relevant

Summarize findings as structured JSON with keys:
  revenue_summary, anomaly_result, top_affected_products, regional_notes, conclusion
"""


def get_sales_agent():
    llm = get_chat_llm()
    return create_react_agent(
        model=llm,
        tools=SALES_TOOLS,
        prompt=_SYSTEM,
    )
