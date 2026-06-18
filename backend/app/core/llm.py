from __future__ import annotations

from functools import lru_cache

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

from app.core.config import get_settings


@lru_cache
def get_chat_llm() -> AzureChatOpenAI:
    s = get_settings()
    return AzureChatOpenAI(
        azure_deployment=s.azure_openai_deployment,
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
        temperature=0,
        streaming=True,
    )


@lru_cache
def get_embeddings() -> AzureOpenAIEmbeddings:
    s = get_settings()
    return AzureOpenAIEmbeddings(
        azure_deployment=s.azure_openai_embedding_deployment,
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
    )
