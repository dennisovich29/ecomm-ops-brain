from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import get_graph, verify_token
from app.core.observability import get_root_handler
from app.graph.state import OpsState
from app.memory.working import get_session_context, save_session_context
from app.models.api import ChatRequest, ChatResponse

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
    thread_id = f"{request.session_id}:{turn_id}"
    state = _build_initial_state(request.content, request.session_id, turn_id)

    ctx = await get_session_context(request.session_id)
    if ctx:
        state["proposed_actions"] = ctx.get("proposed_actions", [])
        if ctx.get("context_summary") or ctx.get("last_query"):
            parts = []
            if ctx.get("last_query"):
                parts.append(f"Previous query: {ctx['last_query']}")
            if ctx.get("context_summary"):
                parts.append(f"Previous analysis summary: {ctx['context_summary'][:400]}")
            state["prior_context"] = "\n".join(parts)

    root_handler = get_root_handler(request.session_id, request.content)
    callbacks = [root_handler] if root_handler else []
    config = {"configurable": {"thread_id": thread_id}, "callbacks": callbacks}
    result = await graph.ainvoke(state, config=config)

    final = result.get("final_response", {})
    await save_session_context(request.session_id, {
        "last_incident_id": result.get("current_incident_id"),
        "context_summary": result.get("root_cause_analysis", ""),
        "proposed_actions": result.get("proposed_actions", []),
        "last_query": request.content,
    })

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
    """SSE streaming endpoint — streams tokens and agent events as text/event-stream."""

    async def event_generator() -> AsyncGenerator[str, None]:
        turn_id = str(uuid.uuid4())
        thread_id = f"{request.session_id}:{turn_id}"
        state = _build_initial_state(request.content, request.session_id, turn_id)

        ctx = await get_session_context(request.session_id)
        if ctx:
            state["proposed_actions"] = ctx.get("proposed_actions", [])
            if ctx.get("context_summary") or ctx.get("last_query"):
                parts = []
                if ctx.get("last_query"):
                    parts.append(f"Previous query: {ctx['last_query']}")
                if ctx.get("context_summary"):
                    parts.append(f"Previous analysis summary: {ctx['context_summary'][:400]}")
                state["prior_context"] = "\n".join(parts)

        root_handler = get_root_handler(request.session_id, request.content)
        callbacks = [root_handler] if root_handler else []
        config = {"configurable": {"thread_id": thread_id}, "callbacks": callbacks}

        try:
            async for event in graph.astream_events(state, config=config, version="v2"):
                msg = _event_to_sse_data(event)
                if msg:
                    yield f"data: {json.dumps(msg)}\n\n"

            # Check whether graph paused at an interrupt (HITL)
            current = await graph.aget_state(config)
            if current.next:
                interrupts = [i for task in current.tasks for i in task.interrupts]
                if interrupts:
                    proposed = interrupts[0].value.get("proposed_actions", [])
                    final_resp = {
                        "type": "approval_pending",
                        "proposed_actions": proposed,
                        "workflow_id": thread_id,
                        "summary": "Review and approve the proposed actions.",
                    }
                    yield f"data: {json.dumps({'type': 'final_response', 'response': final_resp})}\n\n"
                    await save_session_context(request.session_id, {
                        "last_query": request.content,
                        "context_summary": current.values.get("root_cause_analysis", ""),
                        "proposed_actions": current.values.get("proposed_actions", []),
                    })

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event_to_sse_data(event: dict) -> dict | None:
    kind = event.get("event")
    name = event.get("name", "")

    if kind == "on_chat_model_stream":
        # Only stream tokens from synthesize_findings — that's the human-readable
        # RCA markdown. All other nodes (specialist agents, format_response) emit
        # raw JSON that should NOT be shown during streaming.
        node = event.get("metadata", {}).get("langgraph_node", "")
        if node != "synthesize_findings":
            return None
        chunk = event.get("data", {}).get("chunk")
        if chunk and hasattr(chunk, "content") and chunk.content:
            return {"type": "token", "content": chunk.content}

    elif kind == "on_chain_start" and name in (
        "run_sales_agent", "run_inventory_agent",
        "run_marketing_agent", "run_support_agent",
    ):
        return {"type": "agent_start", "agent": name}

    elif kind == "on_chain_end" and name in (
        "run_sales_agent", "run_inventory_agent",
        "run_marketing_agent", "run_support_agent",
    ):
        output = event.get("data", {}).get("output", {})
        domain = name.replace("run_", "").replace("_agent", "")
        return {
            "type": "agent_done",
            "agent": name,
            "findings": output.get(f"{domain}_findings"),
        }

    elif kind == "on_chain_end" and name == "format_response":
        output = event.get("data", {}).get("output", {})
        return {"type": "final_response", "response": output.get("final_response", {})}

    return None
