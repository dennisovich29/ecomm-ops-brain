from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import get_settings

_client: AsyncQdrantClient | None = None

VECTOR_SIZE = 1536  # text-embedding-3-small


def get_qdrant_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncQdrantClient(url=s.qdrant_url)
    return _client


async def ensure_collection() -> None:
    s = get_settings()
    client = get_qdrant_client()
    existing = await client.get_collections()
    names = [c.name for c in existing.collections]
    if s.qdrant_collection not in names:
        await client.create_collection(
            collection_name=s.qdrant_collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


async def close_qdrant() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
