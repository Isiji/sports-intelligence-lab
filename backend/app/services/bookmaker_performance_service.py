# backend/app/services/bookmaker_performance_service.py

from __future__ import annotations

from statistics import mean

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import (
    BookmakerIntelligenceSnapshot,
    Match,
    Prediction,
    PredictionOutcome,
)
from app.intelligence.market_drift_service import (
    analyze_market_drift,
)


MIN_BETS_REQUIRED = 10


def rebuild_bookmaker_intelligence(
    session: Session,
) -> dict:
    session.execute(
        delete(BookmakerIntelligenceSnapshot)
    )

    rows = (
        session.query(
            PredictionOutcome,
            Prediction,
            Match,
        )
        .join(
            Prediction,
            Prediction.id == PredictionOutcome.prediction_id,
        )
        .join(
            Match,
            Match.id == PredictionOutcome.match_id,
        )
        .filter(
            Prediction.odds_bookmaker.isnot(None),
            PredictionOutcome.won.isnot(None),
        )
        .all()
    )

    grouped: dict[str, list[dict]] = {}

    for outcome, prediction, match in rows:
        bookmaker = (
            prediction.odds_bookmaker or "UNKNOWN"
        ).strip()

        grouped.setdefault(bookmaker, []).append(
            {
                "outcome": outcome,
                "prediction": prediction,
                "match": match,
            }
        )

    snapshots_created = 0

    for bookmaker, items in grouped.items():
        bets = len(items)

        if bets <= 0:
            continue

        wins = sum(
            1
            for item in items
            if item["outcome"].won is True
        )

        roi = round(
            sum(
                float(item["outcome"].profit or 0.0)
                for item in items
            )
            / max(bets * 100.0, 1.0),
            6,
        )

        hit_rate = round(
            wins / bets,
            6,
        )

        avg_odds = round(
            mean(
                float(item["outcome"].odds or 0.0)
                for item in items
                if item["outcome"].odds
            ),
            4,
        )

        clv_values = [
            float(item["outcome"].clv)
            for item in items
            if item["outcome"].clv is not None
        ]

        avg_clv = (
            round(mean(clv_values), 6)
            if clv_values
            else 0.0
        )

        positive_clv_rate = (
            round(
                sum(
                    1
                    for value in clv_values
                    if value > 0
                )
                / len(clv_values),
                6,
            )
            if clv_values
            else 0.0
        )

        drift_results = []

        for item in items:
            prediction = item["prediction"]
            match = item["match"]

            if (
                not prediction.odds_market
                or not prediction.odds_selection
            ):
                continue

            try:
                drift = analyze_market_drift(
                    session=session,
                    match_id=prediction.match_id,
                    market=prediction.odds_market,
                    selection=prediction.odds_selection,
                    kickoff_datetime=match.kickoff_datetime,
                )

                drift_results.append(drift)

            except Exception:
                continue

        steam_moves = sum(
            1
            for drift in drift_results
            if drift.steam_move_detected
        )

        sharp_consensus = sum(
            1
            for drift in drift_results
            if drift.sharp_consensus
        )

        high_volatility = sum(
            1
            for drift in drift_results
            if drift.high_volatility_market
        )

        steam_move_accuracy = (
            round(
                steam_moves / len(drift_results),
                6,
            )
            if drift_results
            else 0.0
        )

        sharpness_score = round(
            (
                (positive_clv_rate * 0.4)
                + (hit_rate * 0.3)
                + (steam_move_accuracy * 0.3)
            ),
            6,
        )

        volatility_score = round(
            (
                1.0
                - (
                    high_volatility
                    / max(len(drift_results), 1)
                )
            ),
            6,
        )

        market_efficiency_score = round(
            (
                sharp_consensus
                / max(len(drift_results), 1)
            ),
            6,
        )

        survivability_score = round(
            (
                (hit_rate * 0.35)
                + (roi * 0.35)
                + (positive_clv_rate * 0.30)
            ),
            6,
        )

        confidence_multiplier = _resolve_multiplier(
            survivability_score=survivability_score,
            sharpness_score=sharpness_score,
        )

        bookmaker_tier = _resolve_bookmaker_tier(
            bets=bets,
            survivability_score=survivability_score,
            sharpness_score=sharpness_score,
        )

        session.add(
            BookmakerIntelligenceSnapshot(
                bookmaker=bookmaker,

                bets=bets,

                hit_rate=hit_rate,
                roi=roi,

                avg_odds=avg_odds,

                survivability_score=survivability_score,

                sharpness_score=sharpness_score,

                confidence_multiplier=confidence_multiplier,

                bookmaker_tier=bookmaker_tier,
            )
        )

        snapshots_created += 1

    session.commit()

    return {
        "bookmakers_rebuilt": snapshots_created,
    }


def _resolve_multiplier(
    *,
    survivability_score: float,
    sharpness_score: float,
) -> float:
    score = (
        survivability_score
        + sharpness_score
    ) / 2

    if score >= 0.75:
        return 1.15

    if score >= 0.60:
        return 1.05

    if score >= 0.45:
        return 1.0

    if score >= 0.30:
        return 0.90

    return 0.75


def _resolve_bookmaker_tier(
    *,
    bets: int,
    survivability_score: float,
    sharpness_score: float,
) -> str:
    if bets < MIN_BETS_REQUIRED:
        return "DISCOVERY"

    combined = (
        survivability_score
        + sharpness_score
    ) / 2

    if combined >= 0.80:
        return "ELITE"

    if combined >= 0.65:
        return "STRONG"

    if combined >= 0.50:
        return "STABLE"

    if combined >= 0.35:
        return "WEAK"

    return "AVOID"