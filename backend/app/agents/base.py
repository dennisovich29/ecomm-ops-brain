from __future__ import annotations

from langchain_openai import AzureChatOpenAI
from langchain.tools import BaseTool

from app.core.llm import get_chat_llm
from app.core.observability import get_callbacks


class BaseAgent:
    """Shared setup for all specialist agents."""

    name: str = "base"

    def __init__(self) -> None:
        self._llm: AzureChatOpenAI = get_chat_llm()

    def get_llm_with_tools(self, tools: list[BaseTool]) -> AzureChatOpenAI:
        return self._llm.bind_tools(tools)

    def callbacks(self, session_id: str) -> list:
        return get_callbacks(session_id, self.name)
