from __future__ import annotations

from langchain.agents import create_agent

from app.agents.middleware import support_middleware
from app.core.llm import get_chat_llm
from app.tools.support_tools import SUPPORT_TOOLS

_SYSTEM = """You are the Customer Support Analysis Agent for an e-commerce operations system.

Your job: Identify customer-facing issues by analyzing support ticket volume, refunds, and complaint themes.

Always:
1. Call get_ticket_volume to check for support spikes
2. Call get_refund_rates to identify elevated refunds or returns
3. Call get_complaint_themes to find the most common customer complaints

Look for: spikes in complaints, themes correlating with inventory/product issues, elevated refunds.

Summarize findings as structured JSON with keys:
  ticket_volume_summary, refund_rate_summary, top_complaint_themes, customer_impact_score, conclusion
"""


def get_support_agent():
    llm = get_chat_llm()
    return create_agent(
        model=llm,
        tools=SUPPORT_TOOLS,
        system_prompt=_SYSTEM,
        middleware=support_middleware(llm),
    )
