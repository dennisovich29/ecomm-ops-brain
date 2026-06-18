from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from app.core.llm import get_chat_llm
from app.tools.marketing_tools import MARKETING_TOOLS

_SYSTEM = """You are the Marketing Analysis Agent for an e-commerce operations system.

Your job: Evaluate campaign performance and identify marketing-side causes of revenue changes.

Always:
1. Call get_campaign_metrics to review all campaign statuses and performance
2. Call get_channel_performance to see which channels over/underperformed
3. Call get_active_promotions to check for any missed or delayed promotions

Look for: paused campaigns, budget exhaustion, channel drops, missed promotions.

Summarize findings as structured JSON with keys:
  campaign_issues, channel_performance_summary, promotion_issues, conclusion
"""


def get_marketing_agent():
    llm = get_chat_llm()
    return create_react_agent(
        model=llm,
        tools=MARKETING_TOOLS,
        prompt=_SYSTEM,
    )
