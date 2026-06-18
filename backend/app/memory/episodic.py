from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.db.qdrant import get_qdrant_client
from app.core.config import get_settings
from app.core.llm import get_embeddings


async def _embed(text: str) -> list[float]:
    embeddings = get_embeddings()
    return await embeddings.aembed_query(text)


async def store_incident(state: dict) -> str:
    """Embed and store an incident in Qdrant + Postgres."""
    incident_id = str(uuid.uuid4())
    s = get_settings()
    client = get_qdrant_client()

    # Ensure collection exists before upserting
    from app.db.qdrant import ensure_collection
    await ensure_collection()

    text_repr = _build_incident_text(state)
    vector = await _embed(text_repr)

    payload = {
        "incident_id": incident_id,
        "date": datetime.now(timezone.utc).isoformat(),
        "query": state.get("user_query", ""),
        "root_cause": state.get("root_cause_analysis", ""),
        "domains": (state.get("intent") or {}).get("domains", []),
        "confidence": state.get("confidence_score", 0.0),
        "actions_taken": [
            a.get("action_type") for a in state.get("executed_actions", [])
        ],
    }

    from qdrant_client.models import PointStruct
    await client.upsert(
        collection_name=s.qdrant_collection,
        points=[PointStruct(id=incident_id, vector=vector, payload=payload)],
    )

    # Also persist to Postgres
    try:
        await _persist_incident_to_postgres(incident_id, state)
    except Exception:
        pass  # Qdrant is source of truth for semantic retrieval

    return incident_id


async def retrieve_similar_incidents(query_text: str, top_k: int = 3) -> list[dict]:
    """Retrieve semantically similar past incidents from Qdrant."""
    s = get_settings()
    client = get_qdrant_client()

    # Ensure collection exists — return empty list gracefully if Qdrant is unavailable
    try:
        from app.db.qdrant import ensure_collection
        await ensure_collection()
    except Exception:
        return []

    vector = await _embed(query_text)
    try:
        results = await client.search(
            collection_name=s.qdrant_collection,
            query_vector=vector,
            limit=top_k,
            score_threshold=0.72,
            with_payload=True,
        )
    except Exception:
        return []

    return [
        {
            "incident_id": r.payload.get("incident_id"),
            "date": r.payload.get("date"),
            "query": r.payload.get("query"),
            "root_cause": r.payload.get("root_cause"),
            "domains": r.payload.get("domains", []),
            "confidence": r.payload.get("confidence"),
            "actions_taken": r.payload.get("actions_taken", []),
            "similarity_score": round(r.score, 3),
        }
        for r in results
    ]


def _build_incident_text(state: dict) -> str:
    parts = [state.get("user_query", "")]
    if state.get("root_cause_analysis"):
        parts.append(f"root_cause: {state['root_cause_analysis'][:400]}")
    for domain in ["sales_findings", "inventory_findings", "marketing_findings", "support_findings"]:
        val = state.get(domain)
        if val:
            parts.append(f"{domain}: {json.dumps(val)[:200]}")
    return " | ".join(parts)


async def _persist_incident_to_postgres(incident_id: str, state: dict) -> None:
    from app.db.postgres import get_db_session
    from sqlalchemy import text

    async with get_db_session() as session:
        await session.execute(
            text("""
                INSERT INTO incidents (id, query, root_cause, domains, confidence, embedding_id)
                VALUES (:id, :query, :root_cause, :domains, :confidence, :embedding_id)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": incident_id,
                "query": state.get("user_query", ""),
                "root_cause": state.get("root_cause_analysis", ""),
                "domains": (state.get("intent") or {}).get("domains", []),
                "confidence": state.get("confidence_score", 0.0),
                "embedding_id": incident_id,
            },
        )
        await session.commit()
