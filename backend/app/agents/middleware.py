"""
Reusable LangChain v1 middleware for all specialist agents.

Middleware applies cross-cutting concerns (summarization, PII redaction,
tool error handling) without touching agent business logic.

Usage:
    from app.agents.middleware import agent_middleware, support_middleware

    agent = create_agent(model=llm, tools=TOOLS, system_prompt=_SYSTEM,
                         middleware=agent_middleware(llm))
"""
from __future__ import annotations

import asyncio

from langchain.agents.middleware import (
    AgentMiddleware,
    PIIMiddleware,
    SummarizationMiddleware,
    wrap_tool_call,
)
from langchain.messages import ToolMessage
from langchain_openai import AzureChatOpenAI

# ── Token threshold at which conversation history gets summarised ──────────────
_SUMMARISE_AT_TOKENS = 2_000


# ── Tool error handling ────────────────────────────────────────────────────────

@wrap_tool_call
async def resilient_tool_call(request, handler):
    """Return a graceful error message instead of raising on tool failure.

    Async so it works with both sync and async agent graph invocations.
    Keeps the agent running when a DB or network tool fails transiently — the
    model receives the error text and can continue reasoning with partial data.
    """
    try:
        result = handler(request)
        if asyncio.iscoroutine(result):
            result = await result
        return result
    except Exception as exc:
        return ToolMessage(
            content=(
                f"Tool call failed — {exc}. "
                "Skip this tool and continue with the data already available."
            ),
            tool_call_id=request.tool_call["id"],
        )


# ── PII redaction (support agent) ─────────────────────────────────────────────
# Customer support data may contain real email addresses or phone numbers in
# ticket text.  Redact before sending to the LLM.
# Built-in types: email, credit_card, ip, mac_address, url.
# phone_number requires a custom regex detector per the LangChain v1 API.

_PHONE_REGEX = (
    r"(?:\+?\d{1,3}[\s.-]?)?"
    r"(?:\(?\d{2,4}\)?[\s.-]?)?"
    r"\d{3,4}[\s.-]?\d{4}"
)

_SUPPORT_PII: list[AgentMiddleware] = [
    PIIMiddleware("email", strategy="redact", apply_to_input=True),
    PIIMiddleware("phone_number", detector=_PHONE_REGEX, strategy="redact", apply_to_input=True),
]


# ── Middleware factories ───────────────────────────────────────────────────────

def agent_middleware(llm: AzureChatOpenAI) -> list:
    """Standard middleware stack for sales / inventory / marketing agents."""
    return [
        SummarizationMiddleware(model=llm, trigger=("tokens", _SUMMARISE_AT_TOKENS), keep=("messages", 20)),
        resilient_tool_call,
    ]


def support_middleware(llm: AzureChatOpenAI) -> list:
    """Extended middleware stack for the support agent — includes PII redaction."""
    return [
        *_SUPPORT_PII,
        SummarizationMiddleware(model=llm, trigger=("tokens", _SUMMARISE_AT_TOKENS), keep=("messages", 20)),
        resilient_tool_call,
    ]
