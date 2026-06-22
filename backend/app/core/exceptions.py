from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class GraphNotInitializedError(RuntimeError):
    """Raised when a route is called before the LangGraph workflow is ready."""


class ActionExecutionError(Exception):
    """Raised when resuming the graph with approved actions fails."""
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ApprovalResumeError(Exception):
    """Raised when declining or otherwise resuming an interrupted graph fails."""
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class IncidentQueryError(Exception):
    """Raised when a database query for incident data fails unexpectedly."""
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


async def _handle_graph_not_initialized(request: Request, exc: GraphNotInitializedError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Service unavailable: graph not initialised. Retry shortly."},
    )


async def _handle_action_execution_error(request: Request, exc: ActionExecutionError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"Execution failed: {exc.detail}"})


async def _handle_approval_resume_error(request: Request, exc: ApprovalResumeError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"Resume failed: {exc.detail}"})


async def _handle_incident_query_error(request: Request, exc: IncidentQueryError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"Incident query failed: {exc.detail}"})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(GraphNotInitializedError, _handle_graph_not_initialized)  # type: ignore[arg-type]
    app.add_exception_handler(ActionExecutionError, _handle_action_execution_error)  # type: ignore[arg-type]
    app.add_exception_handler(ApprovalResumeError, _handle_approval_resume_error)  # type: ignore[arg-type]
    app.add_exception_handler(IncidentQueryError, _handle_incident_query_error)  # type: ignore[arg-type]
