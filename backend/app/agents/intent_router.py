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
    action_requested: bool = Field(
        default=False,
        description="True only when the user explicitly requests an action to be performed (restock, pause, resume, fix, create ticket, etc.). False for purely informational queries even if classified HYBRID."
    )


_SYSTEM = """You are an intent classifier for an e-commerce operations AI system.

Read the user's query and classify it using genuine semantic understanding — not keyword matching.
Focus on what the user is actually trying to accomplish.

1. query_type — pick the one that best reflects the user's goal:

   DIAGNOSTIC  — the user wants to understand a situation: root cause, why something changed, what is wrong.
   ACTION      — the user wants a specific change executed and already knows exactly what to do. No investigation needed.
   MEMORY      — the user wants to recall or compare against past incidents.
   SUMMARY     — the user wants a high-level report or overview of current state.
   GENERAL     — purely conversational or clearly unrelated to e-commerce operations.
   HYBRID      — the query combines two or more of the above intent types in a single request.
                 Use this whenever the user is asking for multiple distinct things at once — any combination:
                 diagnosis + action, summary + memory, investigation + report + fix, etc.
                 The number of combined intents does not matter; if it spans more than one, it is HYBRID.

   Prefer ops types over GENERAL when there is any doubt.

2. domains — which of [sales, inventory, marketing, support] are relevant to answering this query.
   Think about what data would actually be needed. For broad or unclear queries, include all domains.
   Missing a domain is worse than including an extra one.

3. time_range — start/end ISO dates. today = {today}, yesterday = {yesterday}. Default to yesterday if unspecified.

4. entities — specific product names, SKU IDs, campaign names, or other named items mentioned.
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

    if not result.time_range.get("start"):
        result.time_range = TimeRange(start=yesterday, end=yesterday)

    return Intent(
        query_type=result.query_type,
        domains=result.domains,
        time_range=result.time_range,
        entities=result.entities,
        action_requested=result.action_requested,
    )
