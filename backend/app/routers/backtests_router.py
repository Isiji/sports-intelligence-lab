# backend/app/routers/backtests_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analysis.backtest_report import build_backtest_report
from app.analysis.weak_markets import get_weak_markets
from app.backtest.calibration import evaluate_confidence_calibration
from app.backtest.evaluate import evaluate_slate_by_group, evaluate_slate_by_market
from app.backtest.rolling import run_rolling_backtest
from app.backtest.settle import settle_and_score
from app.backtest.thresholds import optimize_market_thresholds
from app.db.session import get_session
from app.schemas.backtests import BacktestRunResponse
from app.schemas.calibration import CalibrationBucketResponse
from app.utils.slate import resolve_slate


router = APIRouter(prefix="/backtests", tags=["Backtests"])


@router.post("/settle", response_model=BacktestRunResponse)
def settle_backtest(
    slate: str | None = Query(None),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    try:
        return settle_and_score(session=session, slate=selected_slate)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/groups")
def evaluate_groups(
    slate: str | None = Query(None),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    return evaluate_slate_by_group(session=session, slate=selected_slate)


@router.get("/markets")
def evaluate_markets(
    slate: str | None = Query(None),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    return evaluate_slate_by_market(session=session, slate=selected_slate)


@router.get("/calibration", response_model=list[CalibrationBucketResponse])
def evaluate_calibration(
    slate: str | None = Query(None),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    rows = evaluate_confidence_calibration(
        session=session,
        slate=selected_slate,
    )

    return [CalibrationBucketResponse(**row) for row in rows]


@router.get("/rolling")
def rolling_backtest(
    market: str = Query("home_win"),
    initial_train_size: int = Query(60, ge=30),
    test_window_size: int = Query(20, ge=5),
    session: Session = Depends(get_session),
):
    try:
        return run_rolling_backtest(
            session=session,
            market=market,
            initial_train_size=initial_train_size,
            test_window_size=test_window_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/thresholds")
def optimize_thresholds(
    market: str = Query("home_win"),
    session: Session = Depends(get_session),
):
    return optimize_market_thresholds(
        session=session,
        market=market,
    )


@router.get("/report")
def backtest_report(
    slate: str | None = Query(None),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    return build_backtest_report(session=session, slate=selected_slate)


@router.get("/weak-markets")
def weak_markets(
    min_accuracy: float = Query(0.58),
    min_f1: float = Query(0.45),
    session: Session = Depends(get_session),
):
    return get_weak_markets(
        session=session,
        min_accuracy=min_accuracy,
        min_f1=min_f1,
    )