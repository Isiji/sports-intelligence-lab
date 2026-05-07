# backend/app/routers/value_edges_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analysis.value_edges import get_value_edges
from app.db.session import get_session
from app.schemas.value_edges import ValueEdgeResponse
from app.utils.slate import resolve_slate


router = APIRouter(
    prefix="/value-edges",
    tags=["Value Edges"],
)


@router.get("", response_model=list[ValueEdgeResponse])
def list_value_edges(
    slate: str | None = Query(None),
    min_edge: float = Query(0.05, ge=0.0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    return get_value_edges(
        session=session,
        slate=selected_slate,
        min_edge=min_edge,
        limit=limit,
    )