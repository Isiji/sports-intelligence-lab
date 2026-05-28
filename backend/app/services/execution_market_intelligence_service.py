# backend/app/services/execution_market_intelligence_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, delete
from sqlalchemy.orm import Session

from app.db.models import Prediction, ExecutionMarketIntelligenceSnapshot


CORE_PRODUCTION = "CORE_PRODUCTION"
PRODUCTION_ALLOWED = "PRODUCTION_ALLOWED"
WATCHLIST = "WATCHLIST"
BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ExecutionMarketGate:
    execution_market: str
    verdict: str
    prediction_allowed: bool
    grouping_allowed: bool
    confidence_multiplier: float
    survivability_score: float
    reason: str


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _score_survivability(
    *,
    settled_predictions: int,
    hit_rate: float,
    roi: float,
    avg_odds: float,
    avg_confidence: float,
) -> float:
    sample_score = min(settled_predictions / 80.0, 1.0)

    hit_score = max(0.0, min((hit_rate - 0.38) / 0.27, 1.0))
    roi_score = max(0.0, min((roi + 0.15) / 0.35, 1.0))

    odds_score = 1.0
    if avg_odds >= 5.0:
        odds_score = 0.65
    elif avg_odds >= 3.5:
        odds_score = 0.80
    elif avg_odds <= 1.15:
        odds_score = 0.75

    confidence_score = max(0.0, min((avg_confidence - 0.50) / 0.35, 1.0))

    score = (
        sample_score * 0.25
        + hit_score * 0.30
        + roi_score * 0.30
        + odds_score * 0.10
        + confidence_score * 0.05
    )

    return round(max(0.0, min(score, 1.0)), 4)


def _classify_market(
    *,
    settled_predictions: int,
    hit_rate: float,
    roi: float,
    survivability_score: float,
) -> tuple[str, bool, bool, float, str]:
    if settled_predictions < 8:
        return (
            WATCHLIST,
            True,
            False,
            0.90,
            "Low execution sample. Allowed for prediction discovery, blocked from grouping.",
        )

    if settled_predictions >= 20 and (roi <= -0.12 or hit_rate <= 0.40):
        return (
            BLOCKED,
            False,
            False,
            0.55,
            "Execution market has enough sample and poor survival/profitability.",
        )

    if (
        settled_predictions >= 60
        and roi >= 0.05
        and hit_rate >= 0.56
        and survivability_score >= 0.70
    ):
        return (
            CORE_PRODUCTION,
            True,
            True,
            1.08,
            "Strong execution market with profitable, stable settled performance.",
        )

    if (
        settled_predictions >= 25
        and roi >= 0.00
        and hit_rate >= 0.50
        and survivability_score >= 0.55
    ):
        return (
            PRODUCTION_ALLOWED,
            True,
            True,
            1.00,
            "Execution market is stable enough for prediction and grouping.",
        )

    return (
        WATCHLIST,
        True,
        False,
        0.85,
        "Execution market is still being monitored. Predictions allowed, grouping blocked.",
    )


def rebuild_execution_market_intelligence(
    session: Session,
    *,
    sport: str = "football",
    min_settled: int = 1,
) -> dict:
    rows = session.execute(
        select(
            Prediction.execution_market.label("execution_market"),
            func.count(Prediction.id).label("settled_predictions"),
            func.sum(func.cast(Prediction.is_correct, db_integer())).label("wins"),
            func.avg(Prediction.odds).label("avg_odds"),
            func.sum(func.coalesce(Prediction.profit_loss, 0.0)).label("profit_loss"),
            func.sum(func.coalesce(Prediction.stake, 1.0)).label("total_stake"),
            func.avg(Prediction.confidence).label("avg_confidence"),
        )
        .where(
            Prediction.sport == sport,
            Prediction.execution_market.isnot(None),
            Prediction.execution_market != "",
            Prediction.is_correct.isnot(None),
            Prediction.settled_at.isnot(None),
        )
        .group_by(Prediction.execution_market)
    ).mappings().all()

    session.execute(delete(ExecutionMarketIntelligenceSnapshot).where(
        ExecutionMarketIntelligenceSnapshot.sport == sport
    ))

    inserted = 0
    blocked = 0
    grouped = 0

    for row in rows:
        settled_predictions = int(row["settled_predictions"] or 0)

        if settled_predictions < min_settled:
            continue

        wins = int(row["wins"] or 0)
        losses = max(settled_predictions - wins, 0)

        avg_odds = round(_safe_float(row["avg_odds"]), 4)
        profit_loss = round(_safe_float(row["profit_loss"]), 4)
        total_stake = _safe_float(row["total_stake"], float(settled_predictions))

        hit_rate = round(wins / settled_predictions, 4) if settled_predictions else 0.0
        roi = round(profit_loss / total_stake, 4) if total_stake > 0 else 0.0
        avg_confidence = round(_safe_float(row["avg_confidence"]), 4)

        survivability_score = _score_survivability(
            settled_predictions=settled_predictions,
            hit_rate=hit_rate,
            roi=roi,
            avg_odds=avg_odds,
            avg_confidence=avg_confidence,
        )

        (
            verdict,
            prediction_allowed,
            grouping_allowed,
            confidence_multiplier,
            reason,
        ) = _classify_market(
            settled_predictions=settled_predictions,
            hit_rate=hit_rate,
            roi=roi,
            survivability_score=survivability_score,
        )

        if verdict == BLOCKED:
            blocked += 1

        if grouping_allowed:
            grouped += 1

        session.add(
            ExecutionMarketIntelligenceSnapshot(
                sport=sport,
                execution_market=row["execution_market"],
                settled_predictions=settled_predictions,
                wins=wins,
                losses=losses,
                hit_rate=hit_rate,
                avg_odds=avg_odds,
                profit_loss=profit_loss,
                roi=roi,
                avg_confidence=avg_confidence,
                survivability_score=survivability_score,
                verdict=verdict,
                prediction_allowed=prediction_allowed,
                grouping_allowed=grouping_allowed,
                confidence_multiplier=confidence_multiplier,
                reason=reason,
                updated_at=datetime.utcnow(),
            )
        )

        inserted += 1

    session.commit()

    return {
        "status": "ok",
        "sport": sport,
        "snapshots_rebuilt": inserted,
        "grouping_allowed": grouped,
        "blocked": blocked,
    }


def db_integer():
    from sqlalchemy import Integer
    return Integer


def get_execution_market_gate(
    session: Session,
    execution_market: str | None,
    *,
    sport: str = "football",
) -> ExecutionMarketGate:
    market = (execution_market or "").strip()

    if not market:
        return ExecutionMarketGate(
            execution_market="",
            verdict=WATCHLIST,
            prediction_allowed=True,
            grouping_allowed=False,
            confidence_multiplier=0.90,
            survivability_score=0.0,
            reason="Missing execution market. Prediction discovery allowed, grouping blocked.",
        )

    snapshot = session.scalar(
        select(ExecutionMarketIntelligenceSnapshot).where(
            ExecutionMarketIntelligenceSnapshot.sport == sport,
            ExecutionMarketIntelligenceSnapshot.execution_market == market,
        )
    )

    if not snapshot:
        return ExecutionMarketGate(
            execution_market=market,
            verdict=WATCHLIST,
            prediction_allowed=True,
            grouping_allowed=False,
            confidence_multiplier=0.90,
            survivability_score=0.0,
            reason="No execution intelligence yet. Prediction discovery allowed, grouping blocked.",
        )

    return ExecutionMarketGate(
        execution_market=market,
        verdict=snapshot.verdict,
        prediction_allowed=bool(snapshot.prediction_allowed),
        grouping_allowed=bool(snapshot.grouping_allowed),
        confidence_multiplier=float(snapshot.confidence_multiplier or 1.0),
        survivability_score=float(snapshot.survivability_score or 0.0),
        reason=snapshot.reason or "",
    )


def prediction_execution_allowed(
    session: Session,
    execution_market: str | None,
    *,
    sport: str = "football",
) -> bool:
    return get_execution_market_gate(
        session=session,
        execution_market=execution_market,
        sport=sport,
    ).prediction_allowed


def grouping_execution_allowed(
    session: Session,
    execution_market: str | None,
    *,
    sport: str = "football",
) -> bool:
    return get_execution_market_gate(
        session=session,
        execution_market=execution_market,
        sport=sport,
    ).grouping_allowed