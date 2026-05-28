# backend/app/routers/predictions_router.py

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.db.session import get_session

from app.features.football_features import MARKET_TARGETS

from app.ml.predict_football import (
    predict_all_football_markets,
    predict_football_market,
)

from app.schemas.predictions import (
    PredictionResponse,
    PredictionRunResponse,
)
from app.services.jackpot_1x2_service import (
    analyze_match_1x2,
)

from app.services.prediction_explorer_service import (
    ExplorerFilters,
    search_predictions,
    get_match_intelligence,
    analyze_match_on_demand,
    search_matches,
)

router = APIRouter(
    prefix="/predictions",
    tags=["Predictions"],
)


# =========================================================
# DEFAULT SLATE
# =========================================================

def default_football_slate() -> str:
    return f"football_{date.today().isoformat()}"


# =========================================================
# BASIC PREDICTION LISTING
# =========================================================

@router.get("", response_model=list[PredictionResponse])
def list_predictions(
    slate: str | None = Query(None),
    market: str | None = Query(None),
    min_confidence: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    session: Session = Depends(get_session),
):
    selected_slate = slate or default_football_slate()

    query = (
        select(Prediction)
        .where(
            Prediction.slate == selected_slate,
            Prediction.confidence >= min_confidence,
        )
        .order_by(
            Prediction.confidence.desc(),
            Prediction.id.asc(),
        )
        .limit(limit)
    )

    if market:
        query = query.where(
            Prediction.market == market
        )

    return list(
        session.scalars(query)
    )


# =========================================================
# RUN ALL FOOTBALL PREDICTIONS
# =========================================================

@router.post(
    "/run-football/all",
    response_model=PredictionRunResponse,
)
def run_all_football_predictions(
    slate: str | None = Query(None),

    limit: int = Query(
        30,
        ge=1,
        le=100,
    ),

    min_confidence: float = Query(
        0.6,
        ge=0.5,
        le=0.99,
    ),

    session: Session = Depends(get_session),
):
    selected_slate = slate or default_football_slate()

    inserted = predict_all_football_markets(
        session=session,
        slate=selected_slate,
        limit=limit,
        min_confidence=min_confidence,
    )

    return PredictionRunResponse(
        slate=selected_slate,
        inserted_predictions=inserted,
    )


# =========================================================
# RUN SINGLE MARKET PREDICTIONS
# =========================================================

@router.post(
    "/run-football/{market}",
    response_model=PredictionRunResponse,
)
def run_football_market_predictions(
    market: str,

    slate: str | None = Query(None),

    limit: int = Query(
        30,
        ge=1,
        le=100,
    ),

    min_confidence: float = Query(
        0.6,
        ge=0.5,
        le=0.99,
    ),

    session: Session = Depends(get_session),
):
    if market not in MARKET_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported market: {market}",
        )

    selected_slate = slate or default_football_slate()

    inserted = predict_football_market(
        session=session,
        slate=selected_slate,
        market=market,
        limit=limit,
        min_confidence=min_confidence,
    )

    return PredictionRunResponse(
        slate=selected_slate,
        inserted_predictions=inserted,
    )


# =========================================================
# PREDICTION EXPLORER
# =========================================================

@router.get("/explorer")
def explorer(
    team: str | None = None,

    league: str | None = None,

    market: str | None = None,

    slate: str | None = None,

    date_from: datetime | None = None,

    date_to: datetime | None = None,

    execution_ready_only: bool = False,

    local_only: bool = False,

    temporary_only: bool = False,

    production_only: bool = False,

    min_confidence: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
    ),

    limit: int = Query(
        50,
        ge=1,
        le=500,
    ),

    offset: int = Query(
        0,
        ge=0,
    ),

    session: Session = Depends(get_session),
):
    filters = ExplorerFilters(
        team=team,
        league=league,
        market=market,
        date_from=date_from,
        date_to=date_to,
        execution_ready_only=execution_ready_only,
        local_only=local_only,
        limit=limit,
        offset=offset,
    )

    results = search_predictions(
        session=session,
        filters=filters,
    )

    items = results["items"]

    # ---------------------------------------------
    # Additional filtering
    # ---------------------------------------------

    if slate:
        items = [
            x for x in items
            if x["prediction"].get("slate") == slate
        ]

    if temporary_only:
        items = [
            x for x in items
            if x["prediction"].get("temporary_analysis") is True
        ]

    if production_only:
        items = [
            x for x in items
            if x["prediction"].get("production_status") == "ALLOWED"
        ]

    items = [
        x for x in items
        if (
            x["prediction"].get("confidence") or 0
        ) >= min_confidence
    ]

    results["items"] = items
    results["count"] = len(items)

    return results


# =========================================================
# MATCH PREDICTIONS
# =========================================================

@router.get("/match/{match_id}")
def match_predictions(
    match_id: int,
    session: Session = Depends(get_session),
):
    return get_match_intelligence(
        session=session,
        match_id=match_id,
    )

# =========================================================
# ON-DEMAND MATCH ANALYSIS
# =========================================================

@router.post("/match/{match_id}/analyze")
def analyze_match(
    match_id: int,

    market: str = Query(...),

    save_prediction: bool = False,

    session: Session = Depends(get_session),
):
    if market not in MARKET_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported market: {market}",
        )

    try:
        return analyze_match_on_demand(
            session=session,
            match_id=match_id,
            market=market,
            save_prediction=save_prediction,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# SEARCH MATCHES QUICKLY
# =========================================================

@router.get("/search-matches")
def search_prediction_matches(
    team: str | None = None,

    league: str | None = None,

    date_from: datetime | None = None,

    date_to: datetime | None = None,

    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),

    session: Session = Depends(get_session),
):
    return search_matches(
        session=session,
        team=team,
        league=league,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

# =========================================================
# TOP EXECUTION READY PICKS
# =========================================================

@router.get("/top/execution-ready")
def top_execution_ready_predictions(
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),

    session: Session = Depends(get_session),
):
    filters = ExplorerFilters(
        execution_ready_only=True,
        limit=limit,
    )

    return search_predictions(
        session=session,
        filters=filters,
    )


# =========================================================
# TOP LOCAL REALISM PICKS
# =========================================================

@router.get("/top/local")
def top_local_predictions(
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),

    session: Session = Depends(get_session),
):
    filters = ExplorerFilters(
        local_only=True,
        limit=limit,
    )

    return search_predictions(
        session=session,
        filters=filters,
    )

@router.post(
    "/match/{match_id}/analyze-1x2"
)
def analyze_match_jackpot(
    match_id: int,
    session: Session = Depends(get_session),
):
    try:
        return analyze_match_1x2(
            session=session,
            match_id=match_id,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )