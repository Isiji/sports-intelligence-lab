# backend/app/backtest/settlement_engine.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestRun,
    DynamicLeagueTier,
    LeagueIntelligenceSnapshot,
    Match,
    Prediction,
    PredictionOutcome,
)
from app.services.intelligence_rebuilder import (
    rebuild_confidence_band_intelligence,
    rebuild_league_intelligence,
    rebuild_league_market_intelligence,
    rebuild_market_intelligence,
    rebuild_odds_band_intelligence,
)


DEFAULT_STAKE = 1.0


@dataclass(frozen=True)
class SettlementResult:
    status: str
    won: bool | None
    profit: float
    stake: float
    result_label: str
    reason: str


def settle_and_score(
    session: Session,
    slate: str,
) -> BacktestRun:
    predictions = list(
        session.scalars(
            select(Prediction).where(Prediction.slate == slate)
        )
    )

    if not predictions:
        raise ValueError(f"No predictions found for slate '{slate}'.")

    session.execute(
        delete(PredictionOutcome).where(PredictionOutcome.slate == slate)
    )

    correct = 0
    settled = 0
    total_profit = 0.0
    model_name = predictions[0].model_name

    for prediction in predictions:
        match = session.get(Match, prediction.match_id)

        if not match:
            continue

        settlement = settle_prediction(
            prediction=prediction,
            match=match,
            stake=DEFAULT_STAKE,
        )

        if settlement.status == "PENDING":
            continue

        if settlement.status in {"WON", "LOST", "PUSH"}:
            settled += 1

        if settlement.status == "WON":
            correct += 1

        total_profit += settlement.profit

        _update_prediction_settlement_fields(
            prediction=prediction,
            settlement=settlement,
        )

        session.add(
            PredictionOutcome(
                prediction_id=prediction.id,
                match_id=prediction.match_id,
                slate=prediction.slate,
                league=match.league,
                market=prediction.market,
                predicted_label=prediction.predicted_label,
                confidence=prediction.confidence,
                odds=prediction.odds,
                implied_probability=prediction.implied_probability,
                value_score=prediction.value_score,
                won=settlement.won,
                profit=settlement.profit,
                settled_at=datetime.utcnow(),
            )
        )

    overall_accuracy = correct / settled if settled else 0.0

    run = BacktestRun(
        slate=slate,
        model_name=model_name,
        overall_accuracy=round(overall_accuracy, 4),
        settled_predictions=settled,
    )

    session.add(run)
    session.commit()

    _rebuild_live_intelligence(session)
    rebuild_dynamic_league_tiers(session)

    session.refresh(run)

    print(
        {
            "slate": slate,
            "settled": settled,
            "correct": correct,
            "accuracy": round(overall_accuracy, 4),
            "profit": round(total_profit, 4),
            "roi": round(total_profit / max(settled * DEFAULT_STAKE, 1), 4),
        }
    )

    return run


def settle_prediction(
    *,
    prediction: Prediction,
    match: Match,
    stake: float = DEFAULT_STAKE,
) -> SettlementResult:
    if match.home_goals is None or match.away_goals is None:
        return SettlementResult(
            status="PENDING",
            won=None,
            profit=0.0,
            stake=0.0,
            result_label="PENDING",
            reason="match_not_finished",
        )

    if prediction.odds is None or prediction.odds <= 1:
        return SettlementResult(
            status="VOID",
            won=None,
            profit=0.0,
            stake=0.0,
            result_label="VOID",
            reason="missing_or_invalid_odds",
        )

    result = resolve_prediction_result(
        predicted_label=prediction.predicted_label,
        home_goals=int(match.home_goals),
        away_goals=int(match.away_goals),
    )

    if result.status == "PUSH":
        return SettlementResult(
            status="PUSH",
            won=None,
            profit=0.0,
            stake=stake,
            result_label=result.result_label,
            reason=result.reason,
        )

    if result.status == "VOID":
        return SettlementResult(
            status="VOID",
            won=None,
            profit=0.0,
            stake=0.0,
            result_label=result.result_label,
            reason=result.reason,
        )

    if result.status == "WON":
        return SettlementResult(
            status="WON",
            won=True,
            profit=round((float(prediction.odds) - 1.0) * stake, 6),
            stake=stake,
            result_label=result.result_label,
            reason=result.reason,
        )

    return SettlementResult(
        status="LOST",
        won=False,
        profit=round(-stake, 6),
        stake=stake,
        result_label=result.result_label,
        reason=result.reason,
    )


@dataclass(frozen=True)
class PredictionResult:
    status: str
    result_label: str
    reason: str


def resolve_prediction_result(
    *,
    predicted_label: str,
    home_goals: int,
    away_goals: int,
) -> PredictionResult:
    label = normalize_label(predicted_label)
    total_goals = home_goals + away_goals

    if label == "HOME_WIN":
        return _win_result(home_goals > away_goals, "HOME_WIN")

    if label == "AWAY_WIN":
        return _win_result(away_goals > home_goals, "AWAY_WIN")

    if label == "DRAW":
        return _win_result(home_goals == away_goals, "DRAW")

    if label == "DOUBLE_CHANCE_1X":
        return _win_result(home_goals >= away_goals, "DOUBLE_CHANCE_1X")

    if label == "DOUBLE_CHANCE_X2":
        return _win_result(away_goals >= home_goals, "DOUBLE_CHANCE_X2")

    if label == "DOUBLE_CHANCE_12":
        return _win_result(home_goals != away_goals, "DOUBLE_CHANCE_12")

    if label == "OVER_1_5":
        return _win_result(total_goals > 1.5, "OVER_1_5")

    if label == "UNDER_1_5":
        return _win_result(total_goals < 1.5, "UNDER_1_5")

    if label == "OVER_2_5":
        return _win_result(total_goals > 2.5, "OVER_2_5")

    if label == "UNDER_2_5":
        return _win_result(total_goals < 2.5, "UNDER_2_5")

    if label == "OVER_3_5":
        return _win_result(total_goals > 3.5, "OVER_3_5")

    if label == "UNDER_3_5":
        return _win_result(total_goals < 3.5, "UNDER_3_5")

    if label == "BTTS_YES":
        return _win_result(home_goals > 0 and away_goals > 0, "BTTS_YES")

    if label == "BTTS_NO":
        return _win_result(home_goals == 0 or away_goals == 0, "BTTS_NO")

    if label == "DRAW_NO_BET_HOME":
        return _draw_no_bet_result(
            won=home_goals > away_goals,
            push=home_goals == away_goals,
            result_label="DRAW_NO_BET_HOME",
        )

    if label == "DRAW_NO_BET_AWAY":
        return _draw_no_bet_result(
            won=away_goals > home_goals,
            push=home_goals == away_goals,
            result_label="DRAW_NO_BET_AWAY",
        )

    if label == "HOME_WIN_TO_NIL":
        return _win_result(
            home_goals > away_goals and away_goals == 0,
            "HOME_WIN_TO_NIL",
        )

    if label == "AWAY_WIN_TO_NIL":
        return _win_result(
            away_goals > home_goals and home_goals == 0,
            "AWAY_WIN_TO_NIL",
        )

    if label.startswith("ASIAN_HANDICAP_"):
        return _settle_asian_handicap_result(
            label=label,
            home_goals=home_goals,
            away_goals=away_goals,
        )

    if label.startswith("FIRST_HALF_"):
        return PredictionResult(
            status="VOID",
            result_label=label,
            reason="first_half_market_not_supported_yet",
        )

    if label.startswith("HIGHEST_SCORING_HALF"):
        return PredictionResult(
            status="VOID",
            result_label=label,
            reason="highest_scoring_half_not_supported_yet",
        )

    return PredictionResult(
        status="VOID",
        result_label=label,
        reason="unsupported_market_label",
    )


def _win_result(
    won: bool,
    result_label: str,
) -> PredictionResult:
    return PredictionResult(
        status="WON" if won else "LOST",
        result_label=result_label,
        reason="settled",
    )


def _draw_no_bet_result(
    *,
    won: bool,
    push: bool,
    result_label: str,
) -> PredictionResult:
    if push:
        return PredictionResult(
            status="PUSH",
            result_label=result_label,
            reason="draw_no_bet_push",
        )

    return PredictionResult(
        status="WON" if won else "LOST",
        result_label=result_label,
        reason="settled",
    )


def _settle_asian_handicap_result(
    *,
    label: str,
    home_goals: int,
    away_goals: int,
) -> PredictionResult:
    goal_diff = home_goals - away_goals

    try:
        parts = label.split("_")
        side = parts[2]
        handicap_part = "_".join(parts[3:])
        handicap = _parse_handicap(handicap_part)
    except Exception:
        return PredictionResult(
            status="VOID",
            result_label=label,
            reason="invalid_asian_handicap_label",
        )

    adjusted = (
        goal_diff + handicap
        if side == "HOME"
        else (-goal_diff) + handicap
    )

    if adjusted > 0:
        return PredictionResult(
            status="WON",
            result_label=label,
            reason="settled_asian_handicap",
        )

    if adjusted == 0:
        return PredictionResult(
            status="PUSH",
            result_label=label,
            reason="asian_handicap_push",
        )

    return PredictionResult(
        status="LOST",
        result_label=label,
        reason="settled_asian_handicap",
    )


def _update_prediction_settlement_fields(
    *,
    prediction: Prediction,
    settlement: SettlementResult,
) -> None:
    if hasattr(prediction, "is_correct"):
        prediction.is_correct = settlement.won

    if hasattr(prediction, "result_label"):
        prediction.result_label = settlement.result_label

    if hasattr(prediction, "profit_loss"):
        prediction.profit_loss = settlement.profit

    if hasattr(prediction, "stake"):
        prediction.stake = settlement.stake

    if hasattr(prediction, "settled_at"):
        prediction.settled_at = datetime.utcnow()


def rebuild_dynamic_league_tiers(session: Session) -> None:
    session.execute(delete(DynamicLeagueTier))

    rows = list(session.scalars(select(LeagueIntelligenceSnapshot)))

    for row in rows:
        score = float(row.survivability_score or 0)

        if score >= 45:
            tier = "VERY_STRONG"
        elif score >= 20:
            tier = "STRONG"
        else:
            tier = "WEAK"

        session.add(
            DynamicLeagueTier(
                league=row.league,
                tier=tier,
                strength_score=score,
                profitability_score=float(row.roi or 0),
                stats_quality_score=float(row.stats_quality_score or 0),
                odds_quality_score=float(row.avg_odds or 0),
                survivability_score=score,
                prediction_count=int(row.bets or 0),
            )
        )

    session.commit()


def _rebuild_live_intelligence(session: Session) -> None:
    run_tag = "live_predictions"

    rebuild_market_intelligence(session=session, run_tag=run_tag)
    rebuild_league_intelligence(session=session, run_tag=run_tag)
    rebuild_league_market_intelligence(session=session, run_tag=run_tag)
    rebuild_odds_band_intelligence(session=session, run_tag=run_tag)
    rebuild_confidence_band_intelligence(session=session, run_tag=run_tag)


def normalize_label(label: str) -> str:
    return (
        label.strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )


def is_prediction_correct(
    predicted_label: str,
    home_goals: int,
    away_goals: int,
) -> bool:
    result = resolve_prediction_result(
        predicted_label=predicted_label,
        home_goals=home_goals,
        away_goals=away_goals,
    )

    return result.status == "WON"


def _parse_handicap(handicap_text: str) -> float:
    if handicap_text.startswith("PLUS_"):
        return float(handicap_text.replace("PLUS_", "").replace("_", "."))

    if handicap_text.startswith("MINUS_"):
        return -float(handicap_text.replace("MINUS_", "").replace("_", "."))

    return 0.0