# backend/app/services/execution_settlement_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Match, MatchOdds, Prediction, PredictionOutcome


DEFAULT_STAKE = 100.0


@dataclass(frozen=True)
class ExecutionSettlementResult:
    prediction_id: int
    match_id: int
    model_market: str
    model_pick: str
    execution_market: str
    execution_selection: str
    result_label: str | None
    is_correct: bool | None
    profit_loss: float
    stake: float
    skipped: bool
    reason: str | None = None


def settle_execution_predictions(
    session: Session,
    slate: str,
    stake: float = DEFAULT_STAKE,
    only_execution_ready: bool = True,
) -> dict:
    query = select(Prediction).where(Prediction.slate == slate)

    if only_execution_ready:
        query = query.where(Prediction.execution_ready.is_(True))

    predictions = list(
        session.scalars(
            query.order_by(Prediction.id.asc())
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
            "message": "No execution predictions found.",
        }

    settled = 0
    skipped = 0
    wins = 0
    losses = 0
    total_profit_loss = 0.0
    results: list[ExecutionSettlementResult] = []

    for prediction in predictions:
        result = settle_single_execution_prediction(
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
        "sample_results": [
            result.__dict__
            for result in results[:30]
        ],
    }


def settle_single_execution_prediction(
    session: Session,
    prediction: Prediction,
    stake: float = DEFAULT_STAKE,
) -> ExecutionSettlementResult:
    match = session.get(Match, prediction.match_id)

    if match is None:
        return _skipped(
            prediction=prediction,
            stake=stake,
            reason="match_not_found",
        )

    if not _match_has_final_score(match):
        return _skipped(
            prediction=prediction,
            stake=stake,
            reason="match_unfinished_or_missing_score",
        )

    execution_market = (
        prediction.execution_market
        or prediction.odds_market
        or prediction.market
    )

    execution_selection = (
        prediction.execution_selection
        or prediction.odds_selection
        or prediction.predicted_label
    )

    result_label = resolve_execution_result_label(
        market=execution_market,
        home_goals=int(match.home_goals),
        away_goals=int(match.away_goals),
    )

    is_correct = is_execution_pick_correct(
        market=execution_market,
        selection=execution_selection,
        line=prediction.execution_line,
        home_goals=int(match.home_goals),
        away_goals=int(match.away_goals),
    )

    if is_correct is None:
        return _skipped(
            prediction=prediction,
            stake=stake,
            reason="unsupported_execution_market_for_safe_settlement",
            result_label=result_label,
        )

    odds = float(prediction.odds or 0.0)

    if odds <= 1.0:
        return _skipped(
            prediction=prediction,
            stake=stake,
            reason="missing_or_invalid_odds",
            result_label=result_label,
        )

    profit_loss = calculate_profit_loss(
        won=is_correct,
        odds=odds,
        stake=stake,
    )

    closing_odds = resolve_execution_closing_odds(
        session=session,
        prediction=prediction,
        execution_market=execution_market,
        execution_selection=execution_selection,
    )

    clv = calculate_clv(
        opening_odds=prediction.odds,
        closing_odds=closing_odds,
    )

    now = datetime.utcnow()

    prediction.is_correct = is_correct
    prediction.result_label = result_label
    prediction.profit_loss = profit_loss
    prediction.stake = stake
    prediction.closing_odds = closing_odds
    prediction.clv = clv
    prediction.settled_at = now

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
            market=execution_market,
            predicted_label=execution_selection,
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

    return ExecutionSettlementResult(
        prediction_id=prediction.id,
        match_id=prediction.match_id,
        model_market=prediction.market,
        model_pick=prediction.predicted_label,
        execution_market=execution_market,
        execution_selection=execution_selection,
        result_label=result_label,
        is_correct=is_correct,
        profit_loss=profit_loss,
        stake=stake,
        skipped=False,
    )


def resolve_execution_closing_odds(
    session: Session,
    prediction: Prediction,
    execution_market: str,
    execution_selection: str,
) -> float | None:
    row = session.scalar(
        select(MatchOdds)
        .where(MatchOdds.match_id == prediction.match_id)
        .where(MatchOdds.market == execution_market)
        .where(MatchOdds.selection == execution_selection)
        .order_by(MatchOdds.retrieved_at.desc())
        .limit(1)
    )

    if row is None:
        return None

    return float(row.odds)


def calculate_clv(
    opening_odds: float | None,
    closing_odds: float | None,
) -> float | None:
    if opening_odds is None or closing_odds is None:
        return None

    opening = float(opening_odds)
    closing = float(closing_odds)

    if opening <= 1.0 or closing <= 1.0:
        return None

    return round((opening / closing) - 1.0, 6)


def calculate_profit_loss(
    won: bool,
    odds: float | None,
    stake: float,
) -> float:
    if odds is None or float(odds) <= 1.0:
        return 0.0

    if won:
        return round((float(odds) - 1.0) * stake, 4)

    return round(-stake, 4)


def resolve_execution_result_label(
    market: str,
    home_goals: int,
    away_goals: int,
) -> str:
    market_key = normalize_key(market)
    total_goals = home_goals + away_goals

    if home_goals > away_goals:
        match_result = "HOME_WIN"
    elif away_goals > home_goals:
        match_result = "AWAY_WIN"
    else:
        match_result = "DRAW"

    if "DOUBLE_CHANCE" in market_key:
        return match_result

    if "BTTS" in market_key:
        return "BTTS_YES" if home_goals > 0 and away_goals > 0 else "BTTS_NO"

    if "OVER" in market_key or "UNDER" in market_key:
        return f"TOTAL_GOALS_{total_goals}"

    if "HANDICAP" in market_key or "AH" in market_key or "ASIAN" in market_key:
        return f"HANDICAP_RESULT_{home_goals}_{away_goals}"

    if "DRAW_NO_BET" in market_key:
        return match_result

    return match_result


def is_execution_pick_correct(
    market: str,
    selection: str,
    line: float | None,
    home_goals: int,
    away_goals: int,
) -> bool | None:
    market_key = normalize_key(market)
    selection_key = normalize_key(selection)
    total_goals = home_goals + away_goals

    if selection_key in {"HOME_WIN", "HOME", "1"}:
        return home_goals > away_goals

    if selection_key in {"AWAY_WIN", "AWAY", "2"}:
        return away_goals > home_goals

    if selection_key in {"DRAW", "X"}:
        return home_goals == away_goals

    if selection_key in {"DOUBLE_CHANCE_1X", "1X"}:
        return home_goals >= away_goals

    if selection_key in {"DOUBLE_CHANCE_X2", "X2"}:
        return away_goals >= home_goals

    if selection_key in {"DOUBLE_CHANCE_12", "12"}:
        return home_goals != away_goals

    if selection_key in {"BTTS_YES", "YES"} and "BTTS" in market_key:
        return home_goals > 0 and away_goals > 0

    if selection_key in {"BTTS_NO", "NO"} and "BTTS" in market_key:
        return not (home_goals > 0 and away_goals > 0)

    total_result = settle_total_goals(
        market_key=market_key,
        selection_key=selection_key,
        total_goals=total_goals,
        line=line,
    )

    if total_result is not None:
        return total_result

    handicap_result = settle_handicap(
        market_key=market_key,
        selection_key=selection_key,
        line=line,
        home_goals=home_goals,
        away_goals=away_goals,
    )

    if handicap_result is not None:
        return handicap_result

    draw_no_bet_result = settle_draw_no_bet(
        selection_key=selection_key,
        home_goals=home_goals,
        away_goals=away_goals,
    )

    if draw_no_bet_result is not None:
        return draw_no_bet_result

    return None


def settle_total_goals(
    market_key: str,
    selection_key: str,
    total_goals: int,
    line: float | None,
) -> bool | None:
    resolved_line = line or extract_line_from_key(market_key) or extract_line_from_key(selection_key)

    if resolved_line is None:
        return None

    if "OVER" in selection_key or "OVER" in market_key:
        return total_goals > resolved_line

    if "UNDER" in selection_key or "UNDER" in market_key:
        return total_goals < resolved_line

    return None


def settle_handicap(
    market_key: str,
    selection_key: str,
    line: float | None,
    home_goals: int,
    away_goals: int,
) -> bool | None:
    if not (
        "HANDICAP" in market_key
        or "ASIAN" in market_key
        or market_key.startswith("AH")
        or "HANDICAP" in selection_key
    ):
        return None

    resolved_line = line or extract_line_from_key(selection_key) or extract_line_from_key(market_key)

    if resolved_line is None:
        return None

    if "AWAY" in selection_key or selection_key.endswith("_2"):
        adjusted = away_goals + resolved_line
        return adjusted > home_goals

    if "HOME" in selection_key or selection_key.endswith("_1"):
        adjusted = home_goals + resolved_line
        return adjusted > away_goals

    return None


def settle_draw_no_bet(
    selection_key: str,
    home_goals: int,
    away_goals: int,
) -> bool | None:
    if "DRAW_NO_BET" not in selection_key and "DNB" not in selection_key:
        return None

    if home_goals == away_goals:
        return None

    if "HOME" in selection_key:
        return home_goals > away_goals

    if "AWAY" in selection_key:
        return away_goals > home_goals

    return None


def extract_line_from_key(value: str) -> float | None:
    key = normalize_key(value)

    candidates = [
        "0_25",
        "0_5",
        "0_75",
        "1_0",
        "1_25",
        "1_5",
        "1_75",
        "2_0",
        "2_25",
        "2_5",
        "2_75",
        "3_0",
        "3_5",
        "4_5",
    ]

    sign = -1.0 if "MINUS" in key or "_NEG_" in key else 1.0

    for candidate in candidates:
        if candidate in key:
            return sign * float(candidate.replace("_", "."))

    return None


def _match_has_final_score(match: Match) -> bool:
    return (
        match.home_goals is not None
        and match.away_goals is not None
        and (
            match.is_finished is True
            or normalize_key(match.status)
            in {
                "FINISHED",
                "FT",
                "AET",
                "PEN",
                "MATCH_FINISHED",
            }
        )
    )


def _skipped(
    prediction: Prediction,
    stake: float,
    reason: str,
    result_label: str | None = None,
) -> ExecutionSettlementResult:
    return ExecutionSettlementResult(
        prediction_id=prediction.id,
        match_id=prediction.match_id,
        model_market=prediction.market,
        model_pick=prediction.predicted_label,
        execution_market=(
            prediction.execution_market
            or prediction.odds_market
            or prediction.market
        ),
        execution_selection=(
            prediction.execution_selection
            or prediction.odds_selection
            or prediction.predicted_label
        ),
        result_label=result_label,
        is_correct=None,
        profit_loss=0.0,
        stake=stake,
        skipped=True,
        reason=reason,
    )


def normalize_key(value: object) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
        .replace("/", "_")
    )