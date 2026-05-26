# backend/app/services/prediction_conflict_service.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


HARD_CONFLICT_SCORE = 100.0
MEDIUM_CONFLICT_SCORE = 65.0
SOFT_OVERLAP_SCORE = 35.0


@dataclass
class PredictionConflictResult:
    allowed: bool
    conflict_score: float
    conflict_level: str
    reasons: list[str]
    keep_prediction_id: int | None = None
    reject_prediction_id: int | None = None


def evaluate_prediction_conflict(
    *,
    candidate: dict[str, Any],
    existing_predictions: list[dict[str, Any]],
) -> dict[str, Any]:

    strongest_conflict: PredictionConflictResult | None = None

    for existing in existing_predictions:

        if candidate.get("match_id") != existing.get("match_id"):
            continue

        result = _compare_same_match_predictions(
            candidate=candidate,
            existing=existing,
        )

        if result.conflict_score <= 0:
            continue

        if (
            strongest_conflict is None
            or result.conflict_score > strongest_conflict.conflict_score
        ):
            strongest_conflict = result

    if strongest_conflict is None:
        return asdict(
            PredictionConflictResult(
                allowed=True,
                conflict_score=0.0,
                conflict_level="NONE",
                reasons=[],
            )
        )

    return asdict(strongest_conflict)


def prune_conflicting_predictions(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    accepted: list[dict[str, Any]] = []

    for prediction in sorted(
        predictions,
        key=lambda item: _prediction_strength(item),
        reverse=True,
    ):
        conflict = evaluate_prediction_conflict(
            candidate=prediction,
            existing_predictions=accepted,
        )

        if conflict["allowed"]:
            accepted.append(prediction)

    return accepted


def _compare_same_match_predictions(
    *,
    candidate: dict[str, Any],
    existing: dict[str, Any],
) -> PredictionConflictResult:

    candidate_market = _market(candidate)
    existing_market = _market(existing)

    candidate_label = _label(candidate)
    existing_label = _label(existing)

    reasons: list[str] = []
    score = 0.0

    if _opposite_result_direction(candidate_market, existing_market):
        score = HARD_CONFLICT_SCORE
        reasons.append("opposite match-result direction")

    elif _btts_total_conflict(candidate_market, existing_market):
        score = HARD_CONFLICT_SCORE
        reasons.append("BTTS and goals-total contradiction")

    elif _winner_double_chance_conflict(candidate_market, existing_market):
        score = HARD_CONFLICT_SCORE
        reasons.append("winner conflicts with double-chance protection")

    elif _handicap_direction_conflict(candidate_market, existing_market):
        score = HARD_CONFLICT_SCORE
        reasons.append("opposite handicap exposure")

    elif _same_family_overlap(candidate_market, existing_market):
        score = SOFT_OVERLAP_SCORE
        reasons.append("same execution-family overlap")

    elif candidate_label and existing_label and candidate_label != existing_label:
        if _label_conflict(candidate_label, existing_label):
            score = MEDIUM_CONFLICT_SCORE
            reasons.append("predicted-label contradiction")

    if score <= 0:
        return PredictionConflictResult(
            allowed=True,
            conflict_score=0.0,
            conflict_level="NONE",
            reasons=[],
        )

    keep, reject = _choose_stronger(candidate, existing)

    level = (
        "HARD"
        if score >= HARD_CONFLICT_SCORE
        else "MEDIUM"
        if score >= MEDIUM_CONFLICT_SCORE
        else "SOFT"
    )

    return PredictionConflictResult(
        allowed=score < MEDIUM_CONFLICT_SCORE,
        conflict_score=score,
        conflict_level=level,
        reasons=reasons,
        keep_prediction_id=keep.get("id"),
        reject_prediction_id=reject.get("id"),
    )


def _choose_stronger(
    candidate: dict[str, Any],
    existing: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:

    if _prediction_strength(candidate) >= _prediction_strength(existing):
        return candidate, existing

    return existing, candidate


def _prediction_strength(item: dict[str, Any]) -> float:

    score = 0.0

    score += _safe_float(item.get("execution_score")) * 1.2
    score += _safe_float(item.get("survivability_score")) * 40.0
    score += _safe_float(item.get("local_realism_score")) * 25.0
    score += _safe_float(item.get("confidence")) * 30.0
    score += _safe_float(item.get("value_score")) * 45.0

    if item.get("execution_ready") is True:
        score += 20.0

    odds = _safe_float(item.get("odds"))

    if 1.30 <= odds <= 2.30:
        score += 10.0
    elif odds > 3.80:
        score -= 12.0

    return score


def _market(item: dict[str, Any]) -> str:
    return str(
        item.get("execution_market")
        or item.get("market")
        or ""
    ).lower().strip()


def _label(item: dict[str, Any]) -> str:
    return str(
        item.get("predicted_label")
        or ""
    ).upper().strip()


def _opposite_result_direction(a: str, b: str) -> bool:

    pairs = {
        ("home_win", "away_win"),
        ("home_win", "double_chance_x2"),
        ("away_win", "double_chance_1x"),
        ("draw", "double_chance_12"),
        ("home_away_home", "home_away_away"),
    }

    return (a, b) in pairs or (b, a) in pairs


def _winner_double_chance_conflict(a: str, b: str) -> bool:

    pairs = {
        ("home_win", "double_chance_x2"),
        ("away_win", "double_chance_1x"),
        ("draw", "double_chance_12"),
    }

    return (a, b) in pairs or (b, a) in pairs


def _btts_total_conflict(a: str, b: str) -> bool:

    pairs = {
        ("btts_yes", "under_1_5_goals"),
        ("btts_yes", "under_0_5_goals"),
        ("btts_no", "over_3_5_goals"),
        ("btts_no", "home_over_0_5_goals"),
        ("btts_no", "away_over_0_5_goals"),
    }

    return (a, b) in pairs or (b, a) in pairs


def _handicap_direction_conflict(a: str, b: str) -> bool:

    if not (
        a.startswith("asian_handicap_")
        and b.startswith("asian_handicap_")
    ):
        return False

    a_home = "_home_" in a
    b_home = "_home_" in b

    if a_home == b_home:
        return False

    return True


def _same_family_overlap(a: str, b: str) -> bool:

    return _family(a) == _family(b) and a != b


def _family(market: str) -> str:

    if market.startswith("asian_handicap_"):
        return "asian_handicap"

    if market.startswith("double_chance_"):
        return "double_chance"

    if market.startswith("draw_no_bet_"):
        return "draw_no_bet"

    if market in {"home_win", "draw", "away_win"}:
        return "match_result"

    if market.startswith("over_") or market.startswith("under_"):
        return "goals_total"

    if market.startswith("home_over_") or market.startswith("away_over_"):
        return "team_total"

    if market.startswith("btts_"):
        return "btts"

    if market.startswith("result_total_"):
        return "result_total"

    if market.startswith("handicap_result_"):
        return "handicap_result"

    return market


def _label_conflict(a: str, b: str) -> bool:

    pairs = {
        ("HOME_WIN", "AWAY_WIN"),
        ("HOME_WIN", "NOT_HOME_WIN"),
        ("AWAY_WIN", "NOT_AWAY_WIN"),
        ("DRAW", "NOT_DRAW"),
        ("BTTS_YES", "BTTS_NO"),
        ("OVER_2_5", "UNDER_2_5"),
        ("OVER_1_5", "UNDER_1_5"),
        ("OVER_3_5", "UNDER_3_5"),
    }

    return (a, b) in pairs or (b, a) in pairs


def _safe_float(value: Any) -> float:

    if value is None:
        return 0.0

    try:
        return float(value)

    except (TypeError, ValueError):
        return 0.0