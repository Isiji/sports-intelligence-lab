# backend/app/routers/value_edges_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analysis.value_edges import get_value_edges
from app.db.session import get_session
from app.schemas.value_edges import ValueEdgeResponse


router = APIRouter(
    prefix="/value-edges",
    tags=["Value Edges"],
)


@router.get("", response_model=list[ValueEdgeResponse])
def list_value_edges(
    slate: str = Query("demo"),
    min_edge: float = Query(0.05, ge=0.0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    return get_value_edges(
        session=session,
        slate=slate,
        min_edge=min_edge,
        limit=limit,
    )