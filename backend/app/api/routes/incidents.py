from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import verify_token
from app.core.exceptions import IncidentQueryError
from app.memory.structured import get_incident_by_id, get_incident_list

router = APIRouter()


@router.get("")
async def list_incidents(_: None = Depends(verify_token)) -> JSONResponse:
    """List recent incidents ordered by date descending."""
    try:
        incidents = await get_incident_list(limit=20)
        return JSONResponse({"incidents": incidents})
    except Exception:
        # Return empty list if table doesn't exist or query fails
        return JSONResponse({"incidents": []})


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    _: None = Depends(verify_token),
) -> JSONResponse:
    """Get a single incident with its full action history."""
    try:
        incident = await get_incident_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        return JSONResponse({"incident": incident})
    except HTTPException:
        raise
    except Exception as e:
        raise IncidentQueryError(str(e))
