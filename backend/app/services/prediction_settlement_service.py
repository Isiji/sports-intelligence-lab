# backend/app/services/prediction_settlement_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Match, Prediction, PredictionOutcome
from app.services.intelligence_rebuilder import (
    rebuild_confidence_band_intelligence,
    rebuild_league_intelligence,
    rebuild_league_market_intelligence,
    rebuild_market_intelligence,
    rebuild_odds_band_intelligence,
)


DEFAULT_STAKE = 100.0
LIVE_RUN_TAG = "live_predictions"


@dataclass(frozen=True)
class SettlementResult:
    prediction_id: int
    match_id: int
    market: str
    predicted_label: str
    result_label: str | None
    is_correct: bool | None
    profit_loss: float
    stake: float
    skipped: bool
    reason: str | None = None


def settle_production_predictions(
    session: Session,
    slate: str,
    stake: float = DEFAULT_STAKE,
    rebuild_intelligence: bool = True,
) -> dict:
    predictions = list(
        session.scalars(
            select(Prediction)
            .where(Prediction.slate == slate)
            .order_by(Prediction.id.asc())
        )
    )

    if not predictions:
        return {
            "slate": slate,
            "predictions_found": 0,
            "settled": 0,
            "skipped": 0,
            "wins": 0,
            "losses": 0,
            "profit_loss": 0.0,
            "roi": 0.0,
            "message": "No predictions found for slate.",
        }

    settled = 0
    skipped = 0
    wins = 0
    losses = 0
    total_profit_loss = 0.0
    results: list[SettlementResult] = []

    for prediction in predictions:
        result = settle_single_prediction(
            session=session,
            prediction=prediction,
            stake=stake,
        )

        results.append(result)

        if result.skipped:
            skipped += 1
            continue

        settled += 1
        total_profit_loss += result.profit_loss

        if result.is_correct is True:
            wins += 1
        elif result.is_correct is False:
            losses += 1

    session.commit()

    intelligence_result = None

    if rebuild_intelligence and settled > 0:
        intelligence_result = rebuild_live_prediction_intelligence(
            session=session,
        )

    roi = (
        total_profit_loss / (settled * stake)
        if settled > 0 and stake > 0
        else 0.0
    )

    return {
        "slate": slate,
        "predictions_found": len(predictions),
        "settled": settled,
        "skipped": skipped,
        "wins": wins,
        "losses": losses,
        "profit_loss": round(total_profit_loss, 4),
        "roi": round(roi, 4),
        "stake": stake,
        "intelligence_rebuilt": intelligence_result,
        "sample_results": [
            result.__dict__
            for result in results[:20]
        ],
    }


def settle_single_prediction(
    session: Session,
    prediction: Prediction,
    stake: float = DEFAULT_STAKE,
) -> SettlementResult:
    match = session.get(
        Match,
        prediction.match_id,
    )

    if match is None:
        return SettlementResult(
            prediction_id=prediction.id,
            match_id=prediction.match_id,
            market=prediction.market,
            predicted_label=prediction.predicted_label,
            result_label=None,
            is_correct=None,
            profit_loss=0.0,
            stake=stake,
            skipped=True,
            reason="match_not_found",
        )

    if not _match_has_final_score(match):
        return SettlementResult(
            prediction_id=prediction.id,
            match_id=prediction.match_id,
            market=prediction.market,
            predicted_label=prediction.predicted_label,
            result_label=None,
            is_correct=None,
            profit_loss=0.0,
            stake=stake,
            skipped=True,
            reason="match_unfinished_or_missing_score",
        )

    result_label = resolve_result_label(
        market=prediction.market,
        home_goals=int(match.home_goals),
        away_goals=int(match.away_goals),
    )

    is_correct = is_prediction_correct_for_market(
        market=prediction.market,
        predicted_label=prediction.predicted_label,
        home_goals=int(match.home_goals),
        away_goals=int(match.away_goals),
    )

    if is_correct is None:
        return SettlementResult(
            prediction_id=prediction.id,
            match_id=prediction.match_id,
            market=prediction.market,
            predicted_label=prediction.predicted_label,
            result_label=result_label,
            is_correct=None,
            profit_loss=0.0,
            stake=stake,
            skipped=True,
            reason="unsupported_market_for_safe_settlement",
        )

    profit_loss = calculate_profit_loss(
        won=is_correct,
        odds=prediction.odds,
        stake=stake,
    )

    closing_odds = prediction.odds
    clv = calculate_clv(
        opening_odds=prediction.odds,
        closing_odds=closing_odds,
    )

    now = datetime.utcnow()

    prediction.is_correct = is_correct
    prediction.result_label = result_label
    prediction.profit_loss = profit_loss
    prediction.stake = stake
    prediction.settled_at = now
    prediction.closing_odds = closing_odds
    prediction.clv = clv

    session.execute(
        delete(PredictionOutcome).where(
            PredictionOutcome.prediction_id == prediction.id
        )
    )

    session.add(
        PredictionOutcome(
            prediction_id=prediction.id,
            match_id=prediction.match_id,
            slate=prediction.slate,
            league=match.league,
            market=prediction.market,
            predicted_label=prediction.predicted_label,
            result_label=result_label,
            confidence=prediction.confidence,
            odds=prediction.odds,
            closing_odds=closing_odds,
            clv=clv,
            implied_probability=prediction.implied_probability,
            value_score=prediction.value_score,
            won=is_correct,
            profit=profit_loss,
            stake=stake,
            settled_at=now,
        )
    )

    return SettlementResult(
        prediction_id=prediction.id,
        match_id=prediction.match_id,
        market=prediction.market,
        predicted_label=prediction.predicted_label,
        result_label=result_label,
        is_correct=is_correct,
        profit_loss=profit_loss,
        stake=stake,
        skipped=False,
    )


def rebuild_live_prediction_intelligence(
    session: Session,
) -> dict:
    sync_live_outcomes_to_historical_cache(
        session=session,
        run_tag=LIVE_RUN_TAG,
    )

    results = {}

    results["market"] = rebuild_market_intelligence(
        session=session,
        run_tag=LIVE_RUN_TAG,
    )

    results["league"] = rebuild_league_intelligence(
        session=session,
        run_tag=LIVE_RUN_TAG,
    )

    results["league_market"] = rebuild_league_market_intelligence(
        session=session,
        run_tag=LIVE_RUN_TAG,
    )

    results["odds_band"] = rebuild_odds_band_intelligence(
        session=session,
        run_tag=LIVE_RUN_TAG,
    )

    results["confidence_band"] = rebuild_confidence_band_intelligence(
        session=session,
        run_tag=LIVE_RUN_TAG,
    )

    return results


def sync_live_outcomes_to_historical_cache(
    session: Session,
    run_tag: str = LIVE_RUN_TAG,
) -> None:
    from app.db.models import HistoricalBacktestBet

    session.execute(
        delete(HistoricalBacktestBet).where(
            HistoricalBacktestBet.run_tag == run_tag
        )
    )

    rows = (
        session.query(PredictionOutcome, Match)
        .join(Match, Match.id == PredictionOutcome.match_id)
        .filter(PredictionOutcome.won.isnot(None))
        .all()
    )

    bankroll = 10000.0

    for outcome, match in rows:
        profit = float(outcome.profit or 0.0)
        stake = float(outcome.stake or DEFAULT_STAKE)

        bankroll += profit

        session.add(
            HistoricalBacktestBet(
                run_tag=run_tag,
                match_id=outcome.match_id,
                league=outcome.league,
                home_team=match.home_team,
                away_team=match.away_team,
                market=outcome.market,
                predicted_label=outcome.predicted_label,
                confidence=float(outcome.confidence or 0.0),
                odds=outcome.odds,
                implied_probability=outcome.implied_probability,
                value_score=outcome.value_score,
                won=bool(outcome.won),
                profit=profit,
                bankroll_after_bet=bankroll,
                stake=stake,
            )
        )

    session.commit()


def _match_has_final_score(
    match: Match,
) -> bool:
    return (
        match.home_goals is not None
        and match.away_goals is not None
        and (
            match.is_finished is True
            or str(match.status or "").lower()
            in {
                "finished",
                "ft",
                "aet",
                "pen",
                "match finished",
            }
        )
    )


def normalize_label(
    value: str,
) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )


def resolve_result_label(
    market: str,
    home_goals: int,
    away_goals: int,
) -> str:
    market_key = normalize_label(market)
    total_goals = home_goals + away_goals

    if market_key in {"HOME_WIN", "DRAW", "AWAY_WIN"}:
        if home_goals > away_goals:
            return "HOME_WIN"
        if away_goals > home_goals:
            return "AWAY_WIN"
        return "DRAW"

    if "DOUBLE_CHANCE" in market_key:
        if home_goals > away_goals:
            return "DOUBLE_CHANCE_1X_OR_12"
        if away_goals > home_goals:
            return "DOUBLE_CHANCE_X2_OR_12"
        return "DOUBLE_CHANCE_1X_OR_X2"

    if "BTTS" in market_key:
        return (
            "BTTS_YES"
            if home_goals > 0 and away_goals > 0
            else "BTTS_NO"
        )

    if "1_5" in market_key:
        return "OVER_1_5" if total_goals > 1.5 else "UNDER_1_5"

    if "2_5" in market_key:
        return "OVER_2_5" if total_goals > 2.5 else "UNDER_2_5"

    if "3_5" in market_key:
        return "OVER_3_5" if total_goals > 3.5 else "UNDER_3_5"

    if "DRAW_NO_BET" in market_key:
        if home_goals > away_goals:
            return "DRAW_NO_BET_HOME"
        if away_goals > home_goals:
            return "DRAW_NO_BET_AWAY"
        return "DRAW_NO_BET_VOID"

    return "UNKNOWN"


def is_prediction_correct_for_market(
    market: str,
    predicted_label: str,
    home_goals: int,
    away_goals: int,
) -> bool | None:
    label = normalize_label(predicted_label)
    market_key = normalize_label(market)

    total_goals = home_goals + away_goals

    if label == "HOME_WIN":
        return home_goals > away_goals

    if label == "AWAY_WIN":
        return away_goals > home_goals

    if label == "DRAW":
        return home_goals == away_goals

    if label == "DOUBLE_CHANCE_1X":
        return home_goals >= away_goals

    if label == "DOUBLE_CHANCE_X2":
        return away_goals >= home_goals

    if label == "DOUBLE_CHANCE_12":
        return home_goals != away_goals

    if label in {"OVER_1_5", "OVER_1_5_GOALS"}:
        return total_goals > 1.5

    if label in {"UNDER_1_5", "UNDER_1_5_GOALS"}:
        return total_goals < 1.5

    if label in {"OVER_2_5", "OVER_2_5_GOALS"}:
        return total_goals > 2.5

    if label in {"UNDER_2_5", "UNDER_2_5_GOALS"}:
        return total_goals < 2.5

    if label in {"OVER_3_5", "OVER_3_5_GOALS"}:
        return total_goals > 3.5

    if label in {"UNDER_3_5", "UNDER_3_5_GOALS"}:
        return total_goals < 3.5

    if label == "BTTS_YES":
        return home_goals > 0 and away_goals > 0

    if label == "BTTS_NO":
        return home_goals == 0 or away_goals == 0

    if label == "DRAW_NO_BET_HOME":
        if home_goals == away_goals:
            return None
        return home_goals > away_goals

    if label == "DRAW_NO_BET_AWAY":
        if home_goals == away_goals:
            return None
        return away_goals > home_goals

    if label == "HOME_WIN_TO_NIL":
        return home_goals > away_goals and away_goals == 0

    if label == "AWAY_WIN_TO_NIL":
        return away_goals > home_goals and home_goals == 0

    if (
        "FIRST_HALF" in market_key
        or label.startswith("FIRST_HALF_")
        or label.startswith("HIGHEST_SCORING_HALF")
    ):
        return None

    if label.startswith("ASIAN_HANDICAP_"):
        return None

    return None


def calculate_profit_loss(
    won: bool,
    odds: float | None,
    stake: float,
) -> float:
    if odds is None or odds <= 1:
        return 0.0

    if won:
        return round((float(odds) - 1.0) * stake, 4)

    return round(-stake, 4)


def calculate_clv(
    opening_odds: float | None,
    closing_odds: float | None,
) -> float | None:
    if opening_odds is None or closing_odds is None:
        return None

    if opening_odds <= 0:
        return None

    return round(
        (float(closing_odds) - float(opening_odds)) / float(opening_odds),
        6,
    )