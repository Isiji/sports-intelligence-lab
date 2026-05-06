# backend/app/routers/backtests_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.backtest.calibration import evaluate_confidence_calibration
from app.backtest.evaluate import evaluate_slate_by_group, evaluate_slate_by_market
from app.backtest.settle import settle_and_score
from app.db.session import get_session
from app.schemas.backtests import BacktestRunResponse, GroupBacktestResponse
from app.schemas.calibration import CalibrationBucketResponse


router = APIRouter(prefix="/backtests", tags=["Backtests"])


@router.post("/settle", response_model=BacktestRunResponse)
def settle_backtest(
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    try:
        return settle_and_score(session=session, slate=slate)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/groups")
def evaluate_groups(
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    return evaluate_slate_by_group(session=session, slate=slate)


@router.get("/markets")
def evaluate_markets(
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    return evaluate_slate_by_market(session=session, slate=slate)


@router.get("/calibration", response_model=list[CalibrationBucketResponse])
def evaluate_calibration(
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    rows = evaluate_confidence_calibration(session=session, slate=slate)

    return [CalibrationBucketResponse(**row) for row in rows]