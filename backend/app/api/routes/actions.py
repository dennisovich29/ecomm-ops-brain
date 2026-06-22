from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from langgraph.types import Command

from app.api.deps import get_graph, verify_token
from app.core.exceptions import ActionExecutionError, ApprovalResumeError
from app.models.api import ApprovalRequest, DeclineRequest

router = APIRouter()


@router.post("/approve")
async def approve_actions(
    request: ApprovalRequest,
    graph=Depends(get_graph),
    _: None = Depends(verify_token),
) -> JSONResponse:
    """Resume the interrupted graph with the approved action IDs."""
    config = {"configurable": {"thread_id": request.request_id}}
    try:
        result = await graph.ainvoke(
            Command(resume={"approved_action_ids": request.approved_action_ids}),
            config=config,
        )
        return JSONResponse({
            "status": "executed",
            "request_id": request.request_id,
            "results": result.get("executed_actions", []),
        })
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise ActionExecutionError(str(exc))


@router.post("/decline")
async def decline_actions(
    request: DeclineRequest,
    graph=Depends(get_graph),
    _: None = Depends(verify_token),
) -> JSONResponse:
    """Resume the interrupted graph with no approved actions (decline)."""
    config = {"configurable": {"thread_id": request.request_id}}
    try:
        await graph.ainvoke(
            Command(resume={"approved_action_ids": []}),
            config=config,
        )
        return JSONResponse({"status": "declined", "request_id": request.request_id})
    except Exception as exc:
        raise ApprovalResumeError(str(exc))
