from __future__ import annotations

from datetime import date, timedelta

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.core.llm import get_chat_llm
from app.core.observability import get_callbacks
from app.graph.state import Intent, TimeRange


class IntentOutput(BaseModel):
    query_type: str = Field(
        description="One of: DIAGNOSTIC, ACTION, MEMORY, SUMMARY, HYBRID, GENERAL"
    )
    domains: list[str] = Field(
        description="Relevant domains. Subset of: sales, inventory, marketing, support"
    )
    time_range: TimeRange = Field(
        description="ISO date range the query refers to"
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Named entities: product names, campaign names, SKU IDs, etc."
    )


_SYSTEM = """You are an intent classifier for an e-commerce operations AI system.
Given a user query, extract:
1. query_type: 
   - DIAGNOSTIC (root cause analysis of business issues — e.g. "why did revenue drop", "what's causing the spike")
   - ACTION (execute changes — e.g. "restock X", "pause campaign", "what actions should I take", "what should I do today")
   - MEMORY (retrieve past incidents — e.g. "what happened last time", "show me similar incidents")
   - SUMMARY (generate a report — e.g. "summarize today", "give me an overview")
   - HYBRID (combines ACTION + DIAGNOSTIC — e.g. "diagnose and fix", "find issues and resolve them")
   - GENERAL (purely conversational, identity, or off-topic — e.g. greetings, "who are you", "what is RCA")

When in doubt between GENERAL and an ops type, prefer the ops type.
Only use GENERAL if the query is clearly NOT about e-commerce operations or business performance.

2. domains: which of [sales, inventory, marketing, support] are relevant (empty list for GENERAL)
   - "what should I do today" / "what actions to take" → all domains: [sales, inventory, marketing, support]
   - revenue/orders/products → sales
   - stock/stockout/restock → inventory
   - campaigns/ads/promotions → marketing
   - tickets/complaints/refunds → support

3. time_range: start/end ISO dates. "today" = {today}. "yesterday" = {yesterday}. "last week" = 7 days prior.
4. entities: any specific product names, campaign names, SKU IDs mentioned
"""


async def route_intent(user_query: str, session_id: str = "default") -> Intent:
    yesterday = str(date.today() - timedelta(days=1))
    today = str(date.today())

    llm = get_chat_llm()
    structured_llm = llm.with_structured_output(IntentOutput)
    callbacks = get_callbacks(session_id, "intent_router")

    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM.format(today=today, yesterday=yesterday)),
        ("human", "{query}"),
    ])

    chain = prompt | structured_llm
    result: IntentOutput = await chain.ainvoke({"query": user_query}, config={"callbacks": callbacks})

    # Default time range to yesterday if not set
    if not result.time_range.get("start"):
        result.time_range = TimeRange(start=yesterday, end=yesterday)

    return Intent(
        query_type=result.query_type,
        domains=result.domains,
        time_range=result.time_range,
        entities=result.entities,
    )
