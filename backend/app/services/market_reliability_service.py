# backend/app/services/market_reliability_service.py

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import MarketReliabilitySnapshot, Match, Prediction


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _actual_label(market: str, match: Match) -> str | None:
    if match.home_goals is None or match.away_goals is None:
        return None

    home_goals = match.home_goals
    away_goals = match.away_goals
    total_goals = home_goals + away_goals

    market = _normalize(market)

    if market == "home_win":
        return "home_win" if home_goals > away_goals else "not_home_win"

    if market == "away_win":
        return "away_win" if away_goals > home_goals else "not_away_win"

    if market == "draw":
        return "draw" if home_goals == away_goals else "not_draw"

    if market == "over_2_5_goals":
        return "over_2_5_goals" if total_goals > 2.5 else "under_2_5_goals"

    if market == "under_2_5_goals":
        return "under_2_5_goals" if total_goals < 2.5 else "over_2_5_goals"

    if market == "btts":
        return "btts_yes" if home_goals > 0 and away_goals > 0 else "btts_no"

    return None


def _is_correct(predicted_label: str, actual_label: str) -> bool:
    predicted = _normalize(predicted_label)
    actual = _normalize(actual_label)

    accepted_equivalents = {
        "yes": ["btts_yes"],
        "no": ["btts_no"],
        "home": ["home_win"],
        "away": ["away_win"],
        "x": ["draw"],
        "draw": ["draw"],
        "over": ["over_2_5_goals"],
        "under": ["under_2_5_goals"],
    }

    if predicted == actual:
        return True

    for key, values in accepted_equivalents.items():
        if predicted == key and actual in values:
            return True

    return False


def _sample_score(settled_predictions: int) -> float:
    if settled_predictions >= 1000:
        return 1.0
    if settled_predictions >= 500:
        return 0.85
    if settled_predictions >= 200:
        return 0.7
    if settled_predictions >= 100:
        return 0.55
    if settled_predictions >= 50:
        return 0.35
    if settled_predictions >= 20:
        return 0.2
    return 0.05


def _tier(score: float) -> str:
    if score >= 0.75:
        return "excellent"
    if score >= 0.65:
        return "good"
    if score >= 0.55:
        return "medium"
    if score >= 0.45:
        return "weak"
    return "poor"


def _confidence_multiplier(score: float) -> float:
    if score >= 0.75:
        return 1.0
    if score >= 0.65:
        return 0.9
    if score >= 0.55:
        return 0.75
    if score >= 0.45:
        return 0.55
    return 0.35


def rebuild_market_reliability(session: Session) -> dict:
    markets = (
        session.query(Prediction.sport, Prediction.market)
        .distinct()
        .all()
    )

    updated = 0

    for sport, market in markets:
        predictions = (
            session.query(Prediction, Match)
            .join(Match, Prediction.match_id == Match.id)
            .filter(
                Prediction.sport == sport,
                Prediction.market == market,
                Match.is_finished.is_(True),
                Match.home_goals.isnot(None),
                Match.away_goals.isnot(None),
            )
            .all()
        )

        settled = 0
        correct = 0
        total_confidence = 0.0
        total_value_score = 0.0
        value_count = 0

        for prediction, match in predictions:
            actual = _actual_label(market, match)

            if actual is None:
                continue

            settled += 1
            total_confidence += float(prediction.confidence or 0.0)

            if prediction.value_score is not None:
                total_value_score += float(prediction.value_score)
                value_count += 1

            if _is_correct(prediction.predicted_label, actual):
                correct += 1

        accuracy = round(correct / settled, 4) if settled > 0 else 0.0
        avg_confidence = round(total_confidence / settled, 4) if settled > 0 else 0.0
        avg_value_score = round(total_value_score / value_count, 4) if value_count > 0 else 0.0
        sample_score = _sample_score(settled)

        reliability_score = round(
            (
                accuracy * 0.70
                + sample_score * 0.20
                + min(avg_confidence, 1.0) * 0.10
            ),
            4,
        )

        reliability_tier = _tier(reliability_score)
        prediction_allowed = reliability_score >= 0.45 and settled >= 20
        confidence_multiplier = _confidence_multiplier(reliability_score)

        reason = (
            f"accuracy={accuracy}, settled={settled}, "
            f"sample_score={sample_score}, avg_confidence={avg_confidence}"
        )

        row = (
            session.query(MarketReliabilitySnapshot)
            .filter(
                MarketReliabilitySnapshot.sport == sport,
                MarketReliabilitySnapshot.market == market,
            )
            .first()
        )

        if row is None:
            row = MarketReliabilitySnapshot(
                sport=sport,
                market=market,
                created_at=datetime.utcnow(),
            )
            session.add(row)

        row.settled_predictions = settled
        row.correct_predictions = correct
        row.accuracy = accuracy
        row.avg_confidence = avg_confidence
        row.avg_value_score = avg_value_score
        row.reliability_score = reliability_score
        row.reliability_tier = reliability_tier
        row.prediction_allowed = prediction_allowed
        row.confidence_multiplier = confidence_multiplier
        row.reason = reason
        row.updated_at = datetime.utcnow()

        updated += 1

    session.commit()

    return {
        "message": "Market reliability rebuilt successfully.",
        "markets_updated": updated,
    }


def list_market_reliability(
    session: Session,
    limit: int = 100,
    prediction_allowed: bool | None = None,
    tier: str | None = None,
) -> list[dict]:
    query = session.query(MarketReliabilitySnapshot)

    if prediction_allowed is not None:
        query = query.filter(
            MarketReliabilitySnapshot.prediction_allowed.is_(prediction_allowed)
        )

    if tier:
        query = query.filter(MarketReliabilitySnapshot.reliability_tier == tier)

    rows = (
        query.order_by(
            MarketReliabilitySnapshot.reliability_score.desc(),
            MarketReliabilitySnapshot.settled_predictions.desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "sport": row.sport,
            "market": row.market,
            "settled_predictions": row.settled_predictions,
            "correct_predictions": row.correct_predictions,
            "accuracy": row.accuracy,
            "avg_confidence": row.avg_confidence,
            "avg_value_score": row.avg_value_score,
            "reliability_score": row.reliability_score,
            "reliability_tier": row.reliability_tier,
            "prediction_allowed": row.prediction_allowed,
            "confidence_multiplier": row.confidence_multiplier,
            "reason": row.reason,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]