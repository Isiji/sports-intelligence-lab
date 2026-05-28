# backend/app/services/prediction_alternative_service.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Match
from app.odds.production_label_resolver import (
    resolve_executable_market,
    resolve_execution_market_candidates,
)
from app.services.local_bookmaker_profile_service import (
    evaluate_kenyan_execution,
    preferred_kenyan_fallbacks,
)
from app.services.odds_lookup_service import find_best_odds
from app.services.odds_survivability_service import evaluate_odds_survivability
from app.services.prediction_market_timing_service import analyze_prediction_timing


MAX_ALTERNATIVES = 12
MIN_EXECUTION_SCORE = 55.0
MIN_SURVIVABILITY_SCORE = 0.45
MIN_LOCAL_REALISM_SCORE = 0.20


LOCAL_BOOKMAKER_PRIORITY = {
    "Betika": 1.00,
    "SportPesa": 0.98,
    "Odibets": 0.96,
    "Mozzart": 0.94,
}


SELECTION_MAP = {
    "home_win": "HOME_WIN",
    "draw": "DRAW",
    "away_win": "AWAY_WIN",

    "home_away_home": "HOME_WIN",
    "home_away_away": "AWAY_WIN",

    "double_chance_1x": "DOUBLE_CHANCE_1X",
    "double_chance_x2": "DOUBLE_CHANCE_X2",
    "double_chance_12": "DOUBLE_CHANCE_12",

    "draw_no_bet_home": "DRAW_NO_BET_HOME",
    "draw_no_bet_away": "DRAW_NO_BET_AWAY",

    "over_1_5_goals": "OVER_1_5_GOALS",
    "over_2_5_goals": "OVER_2_5_GOALS",
    "over_3_5_goals": "OVER_3_5_GOALS",
    "under_1_5_goals": "UNDER_1_5_GOALS",
    "under_2_5_goals": "UNDER_2_5_GOALS",
    "under_3_5_goals": "UNDER_3_5_GOALS",

    "btts_yes": "BTTS_YES",
    "btts_no": "BTTS_NO",

    "home_over_0_5_goals": "HOME_OVER_0_5_GOALS",
    "away_over_0_5_goals": "AWAY_OVER_0_5_GOALS",

    "home_clean_sheet": "HOME_CLEAN_SHEET",
    "away_clean_sheet": "AWAY_CLEAN_SHEET",
}


@dataclass
class PredictionAlternative:
    execution_market: str | None
    execution_selection: str | None
    execution_family: str | None
    execution_line: float | None

    bookmaker: str | None
    bookmaker_locality: str | None
    odds: float | None
    odds_market: str | None
    odds_selection: str | None
    odds_match_quality: str | None
    odds_retrieved_at: Any | None

    execution_score: float
    survivability_score: float
    local_realism_score: float
    alternative_score: float

    kenya_available: bool
    kenya_grade: str | None
    kenya_execution_score: float | None
    kenya_value_score: float | None
    kenya_warnings: list[str]
    kenya_reasons: list[str]
    recommended_for_kenya: bool

    timing_status: str | None
    timing_action: str | None

    execution_ready: bool
    reasons: list[str]


def build_prediction_alternatives(
    session: Session,
    *,
    match_id: int,
    target_market: str,
    predicted_label: str | None,
    confidence: float,
    value_score: float | None = None,
    max_alternatives: int = MAX_ALTERNATIVES,
) -> list[dict[str, Any]]:

    match = session.get(Match, match_id)

    if not match:
        return []

    if getattr(match, "is_finished", False):
        return []

    if getattr(match, "is_cancelled", False):
        return []

    if getattr(match, "is_postponed", False):
        return []

    timing = analyze_prediction_timing(
        kickoff_value=getattr(match, "kickoff_datetime", None)
    )

    if timing.recommended_action == "AVOID":
        return []

    executable_market = resolve_executable_market(
        target_market=target_market,
        predicted_label=predicted_label,
    )

    candidate_markets = _expand_candidate_markets(
        target_market=target_market,
        predicted_label=predicted_label,
        executable_market=executable_market,
    )

    alternatives: list[PredictionAlternative] = []

    for candidate_market in candidate_markets:

        resolved_selection = _resolve_candidate_selection(candidate_market)

        result = find_best_odds(
            session=session,
            match_id=match_id,
            market=candidate_market,
            selection=resolved_selection,
            canonical_market=candidate_market,
        )

        if result is None and resolved_selection is not None:
            result = find_best_odds(
                session=session,
                match_id=match_id,
                market=candidate_market,
                selection=None,
                canonical_market=candidate_market,
            )

        if result is None:
            continue

        odds = _safe_float(getattr(result, "odds", None))

        if odds is None:
            continue

        bookmaker = getattr(result, "bookmaker", None)

        survivability = evaluate_odds_survivability(
            market=candidate_market,
            bookmaker=bookmaker,
            odds_retrieved_at=getattr(result, "retrieved_at", None),
            minutes_to_kickoff=timing.minutes_to_kickoff,
        )

        execution_score = _safe_float(
            getattr(result, "execution_score", None),
            0.0,
        )

        local_realism_score = _safe_float(
            getattr(result, "local_realism_score", None),
            0.0,
        )

        survivability_score = _safe_float(
            getattr(survivability, "survivability_score", None),
            0.0,
        )

        execution_market = (
            getattr(result, "executable_market", None)
            or candidate_market
        )

        execution_selection = (
            getattr(result, "executable_selection", None)
            or resolved_selection
            or getattr(result, "provider_selection", None)
        )

        kenya_profile = evaluate_kenyan_execution(
            market=execution_market,
            bookmaker=bookmaker,
            odds=odds,
            confidence=confidence,
            source_market=target_market,
        )

        reasons: list[str] = list(
            getattr(result, "execution_reasons", None) or []
        )

        execution_ready = True

        if execution_score < MIN_EXECUTION_SCORE:
            execution_ready = False
            reasons.append("alternative execution score below minimum")

        if survivability_score < MIN_SURVIVABILITY_SCORE:
            execution_ready = False
            reasons.append("alternative survivability below minimum")

        if getattr(survivability, "stale", False):
            execution_ready = False
            reasons.append("alternative odds are stale")

        if not getattr(survivability, "allowed", True):
            execution_ready = False
            reasons.append("alternative blocked by survivability")

        if local_realism_score < MIN_LOCAL_REALISM_SCORE:
            reasons.append("alternative has weak local realism")

        if kenya_profile["kenya_grade"] == "KENYA_UNAVAILABLE":
            execution_ready = False
            reasons.append("not realistically executable in Kenya")

        if (
            kenya_profile["local_value_score"] is not None
            and kenya_profile["local_value_score"] < -0.04
        ):
            execution_ready = False
            reasons.append("Kenyan odds are strongly value-negative")

        elif (
            kenya_profile["local_value_score"] is not None
            and kenya_profile["local_value_score"] < 0
        ):
            reasons.append("Kenyan odds are slightly value-negative")

        alternative_score = _score_alternative(
            odds=odds,
            bookmaker=bookmaker,
            confidence=confidence,
            value_score=value_score,
            execution_score=execution_score,
            survivability_score=survivability_score,
            local_realism_score=local_realism_score,
            match_quality=getattr(result, "match_quality", None),
            execution_ready=execution_ready,
            kenya_execution_score=float(
                kenya_profile["local_execution_score"] or 0.0
            ),
            kenya_value_score=kenya_profile["local_value_score"],
        )

        alternatives.append(
            PredictionAlternative(
                execution_market=execution_market,
                execution_selection=execution_selection,
                execution_family=getattr(result, "execution_family", None),
                execution_line=getattr(result, "execution_line", None),

                bookmaker=bookmaker,
                bookmaker_locality=getattr(result, "bookmaker_locality", None),
                odds=odds,
                odds_market=getattr(result, "provider_market", None),
                odds_selection=(
                    getattr(result, "provider_selection", None)
                    or execution_selection
                ),
                odds_match_quality=getattr(result, "match_quality", None),
                odds_retrieved_at=getattr(result, "retrieved_at", None),

                execution_score=round(execution_score, 4),
                survivability_score=round(survivability_score, 4),
                local_realism_score=round(local_realism_score, 4),
                alternative_score=round(alternative_score, 4),

                kenya_available=bool(kenya_profile["kenya_available"]),
                kenya_grade=kenya_profile["kenya_grade"],
                kenya_execution_score=round(
                    float(kenya_profile["local_execution_score"]),
                    4,
                ),
                kenya_value_score=kenya_profile["local_value_score"],
                kenya_warnings=kenya_profile["warnings"],
                kenya_reasons=kenya_profile["reasons"],
                recommended_for_kenya=False,

                timing_status=getattr(timing, "status", None),
                timing_action=getattr(timing, "recommended_action", None),

                execution_ready=execution_ready,
                reasons=reasons,
            )
        )

    alternatives = _dedupe_alternatives(alternatives)
    alternatives = _mark_best_kenya_alternative(alternatives)

    alternatives = sorted(
        alternatives,
        key=lambda item: (
            item.recommended_for_kenya is False,
            item.execution_ready is False,
            -float(item.kenya_execution_score or 0.0),
            -item.alternative_score,
            -item.execution_score,
            -item.survivability_score,
            -item.local_realism_score,
            item.odds or 999.0,
        ),
    )

    serialized: list[dict[str, Any]] = []

    for item in alternatives[:max_alternatives]:

        payload = asdict(item)

        retrieved_at = payload.get("odds_retrieved_at")

        if retrieved_at is not None:
            payload["odds_retrieved_at"] = retrieved_at.isoformat()

        serialized.append(payload)

    return serialized


def _resolve_candidate_selection(
    candidate_market: str | None,
) -> str | None:

    if not candidate_market:
        return None

    if candidate_market in SELECTION_MAP:
        return SELECTION_MAP[candidate_market]

    if candidate_market.startswith("asian_handicap_"):
        return candidate_market.upper()

    if candidate_market.startswith("handicap_result_"):
        return candidate_market.upper()

    if candidate_market.startswith("result_total_"):
        return candidate_market.upper()

    if candidate_market.startswith("corners_"):
        return candidate_market.upper()

    if candidate_market.startswith("shots_on_target_"):
        return candidate_market.upper()

    return candidate_market.upper()


def _expand_candidate_markets(
    *,
    target_market: str,
    predicted_label: str | None,
    executable_market: str,
) -> list[str]:

    candidates: list[str] = []

    candidates.extend(
        resolve_execution_market_candidates(
            target_market=target_market,
            predicted_label=predicted_label,
        )
    )

    candidates.append(executable_market)

    candidates.extend(
        preferred_kenyan_fallbacks(executable_market)
    )

    candidates.extend(
        _family_fallbacks(executable_market)
    )

    seen: set[str] = set()
    clean: list[str] = []

    for market in candidates:
        if not market:
            continue

        if market in seen:
            continue

        seen.add(market)
        clean.append(market)

    return clean


def _family_fallbacks(market: str) -> list[str]:

    if market.startswith("asian_handicap_home_"):
        return [
            "asian_handicap_home_0_0",
            "asian_handicap_home_plus_0_25",
            "asian_handicap_home_plus_0_5",
            "asian_handicap_home_plus_0_75",
            "draw_no_bet_home",
            "double_chance_1x",
            "home_win",
            "over_1_5_goals",
        ]

    if market.startswith("asian_handicap_away_"):
        return [
            "asian_handicap_away_0_0",
            "asian_handicap_away_plus_0_25",
            "asian_handicap_away_plus_0_5",
            "asian_handicap_away_plus_0_75",
            "draw_no_bet_away",
            "double_chance_x2",
            "away_win",
            "over_1_5_goals",
        ]

    if market == "home_win":
        return [
            "draw_no_bet_home",
            "double_chance_1x",
            "home_away_home",
            "asian_handicap_home_0_0",
            "asian_handicap_home_plus_0_25",
            "over_1_5_goals",
        ]

    if market == "away_win":
        return [
            "draw_no_bet_away",
            "double_chance_x2",
            "home_away_away",
            "asian_handicap_away_0_0",
            "asian_handicap_away_plus_0_25",
            "over_1_5_goals",
        ]

    if market == "draw":
        return [
            "double_chance_12",
            "under_3_5_goals",
            "under_2_5_goals",
        ]

    if market == "double_chance_1x":
        return [
            "draw_no_bet_home",
            "asian_handicap_home_plus_0_5",
            "asian_handicap_home_plus_0_75",
            "home_win",
            "over_1_5_goals",
        ]

    if market == "double_chance_x2":
        return [
            "draw_no_bet_away",
            "asian_handicap_away_plus_0_5",
            "asian_handicap_away_plus_0_75",
            "away_win",
            "over_1_5_goals",
        ]

    if market == "double_chance_12":
        return [
            "home_away_home",
            "home_away_away",
            "over_1_5_goals",
        ]

    if market.startswith("over_"):
        return [
            "over_1_5_goals",
            "over_2_5_goals",
            "btts_yes",
        ]

    if market.startswith("under_"):
        return [
            "under_3_5_goals",
            "under_2_5_goals",
            "btts_no",
        ]

    if market == "btts_yes":
        return [
            "over_1_5_goals",
            "over_2_5_goals",
            "home_over_0_5_goals",
            "away_over_0_5_goals",
        ]

    if market == "btts_no":
        return [
            "under_3_5_goals",
            "home_clean_sheet",
            "away_clean_sheet",
        ]

    return []


def _mark_best_kenya_alternative(
    alternatives: list[PredictionAlternative],
) -> list[PredictionAlternative]:

    kenya_ready = [
        item
        for item in alternatives
        if item.execution_ready
        and item.kenya_available
        and item.kenya_grade in {
            "KENYA_STRONG",
            "KENYA_ACCEPTABLE",
        }
        and (
            item.kenya_value_score is None
            or item.kenya_value_score >= -0.02
        )
    ]

    if not kenya_ready:
        return alternatives

    best = sorted(
        kenya_ready,
        key=lambda item: (
            -float(item.kenya_execution_score or 0.0),
            -float(item.alternative_score or 0.0),
            -float(item.survivability_score or 0.0),
            -float(item.execution_score or 0.0),
            float(item.odds or 999.0),
        ),
    )[0]

    for item in alternatives:
        item.recommended_for_kenya = (
            item.execution_market == best.execution_market
            and item.execution_selection == best.execution_selection
            and item.bookmaker == best.bookmaker
        )

    return alternatives


def _score_alternative(
    *,
    odds: float | None,
    bookmaker: str | None,
    confidence: float,
    value_score: float | None,
    execution_score: float,
    survivability_score: float,
    local_realism_score: float,
    match_quality: str | None,
    execution_ready: bool,
    kenya_execution_score: float,
    kenya_value_score: float | None,
) -> float:

    score = 0.0

    score += execution_score
    score += survivability_score * 35.0
    score += local_realism_score * 28.0
    score += confidence * 20.0
    score += kenya_execution_score * 0.45

    if value_score is not None:
        score += value_score * 45.0

    if kenya_value_score is not None:
        if kenya_value_score >= 0.05:
            score += 12.0
        elif kenya_value_score >= 0.00:
            score += 5.0
        else:
            score -= min(abs(kenya_value_score) * 80.0, 20.0)

    if bookmaker in LOCAL_BOOKMAKER_PRIORITY:
        score *= LOCAL_BOOKMAKER_PRIORITY[bookmaker]
        score += 10.0

    if match_quality == "exact_executable_market":
        score += 18.0
    elif match_quality == "exact_canonical":
        score += 12.0
    elif match_quality == "asian_handicap_family_fallback":
        score += 7.0
    elif match_quality == "execution_family_fallback":
        score += 4.0

    if odds is not None:
        if 1.30 <= odds <= 2.20:
            score += 12.0
        elif 2.20 < odds <= 3.20:
            score += 5.0
        elif odds > 4.00:
            score -= 18.0
        elif odds < 1.20:
            score -= 15.0

    if not execution_ready:
        score -= 35.0

    return max(score, 0.0)


def _dedupe_alternatives(
    alternatives: list[PredictionAlternative],
) -> list[PredictionAlternative]:

    seen: set[tuple[str | None, str | None, str | None]] = set()
    clean: list[PredictionAlternative] = []

    for item in alternatives:
        key = (
            item.execution_market,
            item.execution_selection,
            item.bookmaker,
        )

        if key in seen:
            continue

        seen.add(key)
        clean.append(item)

    return clean


def _safe_float(
    value: Any,
    default: float | None = None,
) -> float | None:

    if value is None:
        return default

    try:
        return float(value)

    except (TypeError, ValueError):
        return default