# backend/app/routers/model_runs_router.py

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelTrainingRun
from app.db.session import get_session
from app.ml.registry import load_model_metadata
from app.schemas.model_metadata import ActiveModelMetadataResponse
from app.schemas.model_runs import ModelTrainingRunResponse


router = APIRouter(prefix="/model-runs", tags=["Model Runs"])


MODEL_METADATA_PATHS = {
    "home_win": Path("artifacts/football_home_win_model.json"),
    "over_2_5_goals": Path("artifacts/football_over_2_5_model.json"),
}


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


@router.get("/active", response_model=list[ActiveModelMetadataResponse])
def list_active_models():
    active_models = []

    for market, metadata_path in MODEL_METADATA_PATHS.items():
        metadata = load_model_metadata(metadata_path)

        active_models.append(
            ActiveModelMetadataResponse(
                market=market,
                selected_model_name=metadata.get("selected_model_name", "unknown_model"),
                selected_accuracy=metadata.get("selected_accuracy", 0.0),
                feature_columns=metadata.get("feature_columns", []),
            )
        )

    return active_models