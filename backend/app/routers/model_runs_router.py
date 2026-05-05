# backend/app/routers/model_runs_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelTrainingRun
from app.db.session import get_session
from app.schemas.model_runs import ModelTrainingRunResponse


router = APIRouter(prefix="/model-runs", tags=["Model Runs"])


@router.get("", response_model=list[ModelTrainingRunResponse])
def list_model_runs(
    market: str | None = Query(None),
    selected_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    query = select(ModelTrainingRun).order_by(ModelTrainingRun.created_at.desc())

    if market:
        query = query.where(ModelTrainingRun.market == market)

    if selected_only:
        query = query.where(ModelTrainingRun.selected == 1)

    query = query.limit(limit)

    return list(session.scalars(query))