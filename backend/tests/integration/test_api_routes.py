"""
Integration tests — full FastAPI ASGI app with mocked infrastructure.

Strategy:
- Spin up the real FastAPI app (including lifespan startup + shutdown) via
  httpx.AsyncClient + ASGITransport.
- Patch all external connections (Postgres, Qdrant, Redis, LangGraph checkpointer)
  so no real network calls are made.
- Override the ``get_graph`` FastAPI dependency with a deterministic mock graph.
- Auth is bypassed in most tests because the default api_secret_key is "change-me".

Run: pytest tests/integration/ -v -m integration --no-cov
"""
from __future__ import annotations

import contextlib
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


# ══════════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_graph():
    """Deterministic compiled-graph stand-in used by all integration tests."""
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value={
        "final_response": {
            "type": "diagnostic",
            "query": "Why did sales drop?",
            "confidence_score": 0.85,
            "domains_investigated": ["sales", "inventory"],
            "summary": "Sales dropped due to stockouts.",
            "recommendations": ["Restock SKU-001"],
            "proposed_actions": [],
        },
        "executed_actions": [],
        "proposed_actions": [],
        "current_incident_id": "INC-001",
        "root_cause_analysis": "Stockout on SKU-001",
    })

    async def _empty_astream(*args, **kwargs):
        """Async generator that yields nothing — simulates a completed run."""
        return
        yield  # pragma: no cover  # makes this an async generator

    graph.astream = _empty_astream
    graph.aget_state = AsyncMock(return_value=MagicMock(next=[], tasks=[]))
    return graph


@pytest_asyncio.fixture
async def client(mock_graph):
    """Full ASGI app with all external I/O mocked.

    Patches applied:
      Startup  — create_tables, seed_data, ensure_collection, init_checkpointer,
                 init_compiled_graph
      Shutdown — dispose_engine, close_qdrant, close_checkpointer
    The ``get_graph`` FastAPI dependency is overridden via dependency_overrides.
    """
    from app.api.deps import get_graph

    with contextlib.ExitStack() as stack:
        # ── Startup hooks ──────────────────────────────────────────────────
        stack.enter_context(patch("app.db.postgres.create_tables", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.postgres.seed_data", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.qdrant.ensure_collection", new_callable=AsyncMock))
        stack.enter_context(
            patch("app.db.checkpointer.init_checkpointer",
                  new_callable=AsyncMock, return_value=MagicMock())
        )
        stack.enter_context(patch("app.graph.workflow.init_compiled_graph"))

        # ── Shutdown hooks ─────────────────────────────────────────────────
        stack.enter_context(patch("app.db.postgres.dispose_engine", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.qdrant.close_qdrant", new_callable=AsyncMock))
        stack.enter_context(
            patch("app.db.checkpointer.close_checkpointer", new_callable=AsyncMock)
        )

        from app.main import create_app
        app = create_app()

        # Use dependency_overrides — the canonical FastAPI way to swap deps.
        app.dependency_overrides[get_graph] = lambda: mock_graph

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Health endpoints
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
async def test_health_ok(client):
    """GET /health always returns 200 {"status": "ok"}."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.integration
async def test_ready_degraded_when_services_down(client):
    """GET /ready returns 503 with degraded status when services are unavailable."""
    with patch("app.db.postgres.get_db_session") as mock_db_ctx, \
         patch("app.db.qdrant.get_qdrant_client") as mock_qdrant:

        mock_db_ctx.return_value.__aenter__ = AsyncMock(
            side_effect=ConnectionRefusedError("no postgres")
        )
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_qdrant.return_value.get_collections = AsyncMock(
            side_effect=ConnectionRefusedError("no qdrant")
        )

        resp = await client.get("/ready")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert "postgres" in body["checks"]
    assert "qdrant" in body["checks"]
    assert all("error" in v for v in body["checks"].values())


@pytest.mark.integration
async def test_ready_ok_when_all_services_up(client):
    """GET /ready returns 200 {"status": "ready"} when all services respond."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_collections = AsyncMock()

    with patch("app.db.postgres.get_db_session") as mock_db_ctx, \
         patch("app.db.qdrant.get_qdrant_client") as mock_qdrant:

        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_qdrant.return_value.get_collections = AsyncMock(return_value=mock_collections)

        resp = await client.get("/ready")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Auth enforcement
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
async def test_chat_requires_auth_when_secret_key_configured(mock_graph):
    """POST /chat returns 401 when a real secret key is set and token is missing."""
    from app.api.deps import get_graph
    from app.core.config import Settings

    mock_settings = Settings(
        azure_openai_api_key="test-key",
        azure_openai_endpoint="https://test.openai.azure.com",
        azure_openai_deployment="gpt-4o",
        api_secret_key="super-secret-token",
    )

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("app.db.postgres.create_tables", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.postgres.seed_data", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.qdrant.ensure_collection", new_callable=AsyncMock))
        stack.enter_context(
            patch("app.db.checkpointer.init_checkpointer",
                  new_callable=AsyncMock, return_value=MagicMock())
        )
        stack.enter_context(patch("app.graph.workflow.init_compiled_graph"))
        stack.enter_context(patch("app.db.postgres.dispose_engine", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.qdrant.close_qdrant", new_callable=AsyncMock))
        stack.enter_context(
            patch("app.db.checkpointer.close_checkpointer", new_callable=AsyncMock)
        )
        stack.enter_context(
            patch("app.core.config.get_settings", return_value=mock_settings)
        )
        # Also patch where verify_token actually calls it (lru_cache means the cached
        # result for the test env has api_secret_key="change-me"; patching the
        # local reference in deps is the reliable way to override it).
        stack.enter_context(
            patch("app.api.deps.get_settings", return_value=mock_settings)
        )

        from app.main import create_app
        app = create_app()
        app.dependency_overrides[get_graph] = lambda: mock_graph

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/chat",
                json={"content": "Why did sales drop yesterday?"},
            )

        app.dependency_overrides.clear()

    assert resp.status_code == 401


@pytest.mark.integration
async def test_chat_accepts_valid_bearer_token(mock_graph):
    """POST /chat succeeds when the correct Bearer token is provided."""
    from app.api.deps import get_graph
    from app.core.config import Settings

    mock_settings = Settings(
        azure_openai_api_key="test-key",
        azure_openai_endpoint="https://test.openai.azure.com",
        azure_openai_deployment="gpt-4o",
        api_secret_key="super-secret-token",
    )

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("app.db.postgres.create_tables", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.postgres.seed_data", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.qdrant.ensure_collection", new_callable=AsyncMock))
        stack.enter_context(
            patch("app.db.checkpointer.init_checkpointer",
                  new_callable=AsyncMock, return_value=MagicMock())
        )
        stack.enter_context(patch("app.graph.workflow.init_compiled_graph"))
        stack.enter_context(patch("app.db.postgres.dispose_engine", new_callable=AsyncMock))
        stack.enter_context(patch("app.db.qdrant.close_qdrant", new_callable=AsyncMock))
        stack.enter_context(
            patch("app.db.checkpointer.close_checkpointer", new_callable=AsyncMock)
        )
        stack.enter_context(
            patch("app.core.config.get_settings", return_value=mock_settings)
        )
        stack.enter_context(
            patch("app.api.deps.get_settings", return_value=mock_settings)
        )

        from app.main import create_app
        app = create_app()
        app.dependency_overrides[get_graph] = lambda: mock_graph

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/chat",
                json={"content": "Why did sales drop yesterday?"},
                headers={"Authorization": "Bearer super-secret-token"},
            )

        app.dependency_overrides.clear()

    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 3. Chat endpoint
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
async def test_chat_returns_correct_shape(client):
    """POST /chat returns a response with session_id, turn_id, and response keys."""
    resp = await client.post(
        "/chat",
        json={"content": "Why did sales drop yesterday?", "session_id": "sess-integration-01"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert body["session_id"] == "sess-integration-01"
    assert "turn_id" in body
    assert "response" in body


@pytest.mark.integration
async def test_chat_auto_generates_session_id(client):
    """POST /chat without session_id auto-generates one."""
    resp = await client.post(
        "/chat",
        json={"content": "Give me a summary of performance"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert len(body["session_id"]) > 0


@pytest.mark.integration
async def test_chat_validates_content_too_short(client):
    """POST /chat with empty content returns 422 (min_length=1)."""
    resp = await client.post("/chat", json={"content": ""})
    assert resp.status_code == 422


@pytest.mark.integration
async def test_chat_invokes_graph_with_state(client, mock_graph):
    """POST /chat calls graph.ainvoke exactly once with valid OpsState."""
    await client.post(
        "/chat",
        json={"content": "What are the top stockout issues today?", "session_id": "sess-check"},
    )
    mock_graph.ainvoke.assert_called_once()
    call_args = mock_graph.ainvoke.call_args
    state = call_args[0][0]  # first positional arg is the state dict
    assert state["user_query"] == "What are the top stockout issues today?"
    assert state["session_id"] == "sess-check"


@pytest.mark.integration
async def test_chat_uses_session_id_as_thread_id(client, mock_graph):
    """POST /chat passes session_id as thread_id so LangGraph loads prior turns."""
    resp = await client.post(
        "/chat",
        json={"content": "What should I do now?", "session_id": "sess-prior"},
    )
    assert resp.status_code == 200
    # Conversation history is carried by the LangGraph checkpointer via thread_id
    call_config = mock_graph.ainvoke.call_args.kwargs["config"]
    assert call_config["configurable"]["thread_id"] == "sess-prior"


@pytest.mark.integration
async def test_chat_stream_returns_event_stream(client):
    """POST /chat/stream returns 200 with text/event-stream content type."""
    resp = await client.post(
        "/chat/stream",
        json={"content": "Give me a status update", "session_id": "sess-stream"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Actions endpoints
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
async def test_approve_actions_returns_executed(client, mock_graph):
    """POST /actions/approve resumes graph and returns executed actions."""
    mock_graph.ainvoke = AsyncMock(return_value={
        "executed_actions": [{"action_id": "act-001", "type": "restock_product"}],
    })
    resp = await client.post(
        "/actions/approve",
        json={"request_id": "thread-abc", "approved_action_ids": ["act-001"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "executed"
    assert body["request_id"] == "thread-abc"
    assert isinstance(body["results"], list)


@pytest.mark.integration
async def test_approve_actions_value_error_returns_404(client, mock_graph):
    """POST /actions/approve returns 404 when graph raises ValueError (bad thread_id)."""
    mock_graph.ainvoke = AsyncMock(side_effect=ValueError("Thread not found"))
    resp = await client.post(
        "/actions/approve",
        json={"request_id": "bad-thread", "approved_action_ids": []},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_approve_actions_server_error_returns_500(client, mock_graph):
    """POST /actions/approve returns 500 on unexpected graph failure."""
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("DB exploded"))
    resp = await client.post(
        "/actions/approve",
        json={"request_id": "thread-err", "approved_action_ids": []},
    )
    assert resp.status_code == 500


@pytest.mark.integration
async def test_decline_actions_returns_declined(client, mock_graph):
    """POST /actions/decline resumes graph with empty approved list."""
    mock_graph.ainvoke = AsyncMock(return_value={})
    resp = await client.post(
        "/actions/decline",
        json={"request_id": "thread-decline"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "declined"
    assert body["request_id"] == "thread-decline"


@pytest.mark.integration
async def test_decline_actions_server_error_returns_500(client, mock_graph):
    """POST /actions/decline returns 500 on graph failure."""
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Graph error"))
    resp = await client.post(
        "/actions/decline",
        json={"request_id": "thread-fail"},
    )
    assert resp.status_code == 500


# ══════════════════════════════════════════════════════════════════════════════
# 5. Incidents endpoints
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
async def test_incidents_list_empty(client):
    """GET /incidents returns 200 with empty list when no incidents exist."""
    with patch("app.memory.structured.get_incident_list",
               new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/incidents")
    assert resp.status_code == 200
    assert resp.json() == {"incidents": []}


@pytest.mark.integration
async def test_incidents_list_with_data(client):
    """GET /incidents returns list of incident dicts."""
    fake_incidents = [
        {"incident_id": "INC-001", "query": "Sales drop", "date": "2026-06-18T00:00:00Z"},
        {"incident_id": "INC-002", "query": "Stockout", "date": "2026-06-17T00:00:00Z"},
    ]
    with patch("app.memory.structured.get_incident_list",
               new_callable=AsyncMock, return_value=fake_incidents):
        resp = await client.get("/incidents")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["incidents"]) == 2
    assert body["incidents"][0]["incident_id"] == "INC-001"


@pytest.mark.integration
async def test_incident_by_id_found(client):
    """GET /incidents/{id} returns 200 with incident data when found."""
    fake_incident = {
        "incident_id": "INC-001",
        "query": "Why did sales drop?",
        "root_cause": "Stockout on SKU-001",
        "actions": [],
    }
    with patch("app.memory.structured.get_incident_by_id",
               new_callable=AsyncMock, return_value=fake_incident):
        resp = await client.get("/incidents/INC-001")
    assert resp.status_code == 200
    assert resp.json()["incident"]["incident_id"] == "INC-001"


@pytest.mark.integration
async def test_incident_by_id_not_found(client):
    """GET /incidents/{id} returns 404 when incident does not exist."""
    with patch("app.memory.structured.get_incident_by_id",
               new_callable=AsyncMock, return_value=None):
        resp = await client.get("/incidents/INC-MISSING")
    assert resp.status_code == 404


@pytest.mark.integration
async def test_incident_by_id_db_error_returns_500(client):
    """GET /incidents/{id} returns 500 on unexpected DB failure."""
    with patch("app.memory.structured.get_incident_by_id",
               new_callable=AsyncMock, side_effect=RuntimeError("DB down")):
        resp = await client.get("/incidents/INC-ERR")
    assert resp.status_code == 500
