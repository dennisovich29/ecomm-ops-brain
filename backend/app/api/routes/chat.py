from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import get_graph, verify_token
from app.core.observability import get_root_handler
from app.graph.state import OpsState
from app.models.api import ChatRequest

router = APIRouter()


def _build_initial_state(query: str, session_id: str, turn_id: str) -> OpsState:
    return OpsState(
        user_query=query,
        session_id=session_id,
        turn_id=turn_id,
        intent=None,
        active_agents=[],
        sales_findings=None,
        inventory_findings=None,
        marketing_findings=None,
        support_findings=None,
        reflection_notes=[],
        confidence_score=0.0,
        gaps_identified=[],
        reflection_passes=0,
        similar_incidents=[],
        current_incident_id=None,
        proposed_actions=[],
        approved_actions=[],
        executed_actions=[],
        root_cause_analysis=None,
        recommendations=[],
        final_response=None,
        prior_context=None,
        messages=[],
    )


@router.post("")
async def chat(
    request: ChatRequest,
    graph=Depends(get_graph),
    _: None = Depends(verify_token),
) -> JSONResponse:
    """Synchronous chat endpoint — runs full graph and returns final response."""
    turn_id = str(uuid.uuid4())
    thread_id = request.session_id  # persistent per-session thread for conversation history
    state = _build_initial_state(request.content, request.session_id, turn_id)
    root_handler = get_root_handler(request.session_id, request.content)
    callbacks = [root_handler] if root_handler else []
    config = {"configurable": {"thread_id": thread_id}, "callbacks": callbacks}
    result = await graph.ainvoke(state, config=config)

    final = result.get("final_response", {})

    return JSONResponse({
        "session_id": request.session_id,
        "turn_id": turn_id,
        "response": final,
    })


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    graph=Depends(get_graph),
) -> StreamingResponse:
    """SSE streaming endpoint — LangGraph native astream with values + messages modes."""

    async def event_generator() -> AsyncGenerator[str, None]:
        turn_id = str(uuid.uuid4())
        thread_id = request.session_id  # persistent per-session thread for conversation history
        state = _build_initial_state(request.content, request.session_id, turn_id)
        root_handler = get_root_handler(request.session_id, request.content)
        callbacks = [root_handler] if root_handler else []
        config = {"configurable": {"thread_id": thread_id}, "callbacks": callbacks}

        last_state: dict = {}

        try:
            async for mode, data in graph.astream(
                state, config=config, stream_mode=["values", "messages"]
            ):
                if mode == "messages":
                    msg, meta = data
                    if meta.get("langgraph_node") == "synthesize_findings":
                        content = getattr(msg, "content", None)
                        if content and isinstance(content, str):
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                elif mode == "values":
                    last_state = data

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            return

        # Detect HITL interrupt: graph paused with pending nodes
        snapshot = await graph.aget_state(config)
        if snapshot and snapshot.next:
            # proposed_actions live in the checkpointer — no need to pass them here,
            # the approve/decline routes load them via Command(resume=...) + thread_id
            final = {
                "type": "approval_pending",
                "proposed_actions": last_state.get("proposed_actions", []),
                "workflow_id": thread_id,
                "summary": "Review and approve the proposed actions.",
            }
        else:
            final = last_state.get("final_response", {})

        yield f"data: {json.dumps({'type': 'final_response', 'response': final})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
