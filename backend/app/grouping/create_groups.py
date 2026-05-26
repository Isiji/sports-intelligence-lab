# backend/app/grouping/create_groups.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import prod
from statistics import mean
from typing import Any
from app.services.odds_survivability_service import (
    evaluate_odds_survivability,
)
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session
from app.services.prediction_market_timing_service import analyze_prediction_timing

from app.backtest.portfolio_profiles import PROFILE_CONFIGS
from app.db.models import Prediction, PredictionGroupItem
from app.grouping.profitability_intelligence import (
    IntelligenceConfig,
    confidence_band,
    load_confidence_band_intelligence,
    load_league_market_intelligence,
    load_market_intelligence,
    load_odds_band_intelligence,
    odds_band,
)
from app.intelligence.correlation_rules import evaluate_group_correlation
from app.intelligence.exposure_control import apply_exposure_controls
from app.intelligence.pick_recommendation_engine import build_recommendation_layer
from app.intelligence.portfolio_filters import (
    PortfolioFilterContext,
    build_portfolio_filter_context,
    evaluate_pick_for_portfolio,
)
from app.intelligence.stake_engine import (
    calculate_group_stake,
    resolve_group_tier,
)
from app.services.live_group_validation_service import (
    validate_group_for_execution,
)
from app.services.prediction_conflict_service import (
    evaluate_prediction_conflict,
)
from app.odds.executable_market_registry import parse_executable_market
from app.odds.market_quality_engine import get_enabled_markets
from app.services.league_production_filter_service import (
    filter_candidate_dicts_by_league_quality,
)
from app.services.production_pick_scoring_service import score_pick_list



GROUPING_DEBUG = False
GROUPING_DIAGNOSTICS = True

MAX_RAW_CANDIDATES = 500
MAX_ENRICHMENT_CANDIDATES = 250
MAX_UNIQUE_MATCH_CANDIDATES = 120
MAX_APPROVED_CANDIDATES = 60

MIN_GAMES_PER_GROUP = 2
MAX_GAMES_PER_GROUP = 3
MAX_GROUPS = 4

PRODUCTION_MIN_GROUP_ODDS = 2.0
PRODUCTION_MAX_GROUP_ODDS = 35.0

DEFAULT_GROUPING_BANKROLL = 10_000.0
DEFAULT_FLAT_STAKE = 100.0

STRICT_GROUPING_MIN_CONFIDENCE = 0.60
STRICT_GROUPING_MIN_VALUE_SCORE = 0.03
STRICT_MIN_PRODUCTION_SCORE = 66.0
STRICT_MAX_PORTFOLIO_RISK = 28.0
ADAPTIVE_MAX_PORTFOLIO_RISK = 42.0

IMMATURE_INTELLIGENCE_CONFIDENCE_FLOOR = 0.64
IMMATURE_INTELLIGENCE_VALUE_FLOOR = 0.06

AUTO_PROFILE_LADDERS = {
    "AUTO_SAFE": [
        "SAFE_B_CURRENT_BEST",
        "SAFE_C_HIGHER_CONF",
        "SAFE_D_MORE_ROOM",
        "BALANCED_REFERENCE",
    ],
}


@dataclass(frozen=True)
class PortfolioGroupConfig:
    max_groups: int = MAX_GROUPS
    min_group_size: int = MIN_GAMES_PER_GROUP
    max_group_size: int = MAX_GAMES_PER_GROUP

    league_odds_filter_mode: str = "strict"

    min_confidence: float = STRICT_GROUPING_MIN_CONFIDENCE
    min_value_score: float = STRICT_GROUPING_MIN_VALUE_SCORE

    min_odds: float = 1.50
    max_odds: float = 5.20

    min_group_odds: float = PRODUCTION_MIN_GROUP_ODDS
    max_group_odds: float = PRODUCTION_MAX_GROUP_ODDS

    min_market_roi: float = -0.05
    min_league_roi: float = -0.08
    min_band_roi: float = -0.08

    max_same_family_per_group: int = 4
    min_sample_size: int = 10

    max_same_market_per_group: int = 4
    max_same_league_per_group: int = 2

    use_intelligence_filters: bool = True

    bankroll: float = DEFAULT_GROUPING_BANKROLL
    flat_stake: float = DEFAULT_FLAT_STAKE


def _debug(*args: Any) -> None:
    if GROUPING_DEBUG:
        print(*args)


def _diag(stage: str, value: Any) -> None:
    if GROUPING_DIAGNOSTICS:
        print(f"[GROUPING:{stage}] {value}")


def _format_kickoff_time(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    return str(value)


def _candidate_kickoff_time(candidate: dict[str, Any]) -> str | None:
    return _format_kickoff_time(
        candidate.get("kickoff_time")
        or candidate.get("kickoff_datetime")
        or candidate.get("kickoff_date")
    )


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_not_inversion_label(label: Any) -> bool:
    return str(label or "").upper().startswith("NOT_")


def _render_executable_label(item: dict[str, Any]) -> str:
    predicted_label = str(item.get("predicted_label") or "")
    odds_selection = str(item.get("odds_selection") or "")
    odds_market = str(item.get("odds_market") or "")
    bookmaker = str(item.get("odds_bookmaker") or "")

    if _is_not_inversion_label(predicted_label) and odds_selection:
        return f"{odds_selection} via inversion of {predicted_label}"

    if odds_selection:
        return odds_selection

    return predicted_label


def _resolve_group_market_family(market: str) -> str:
    return parse_executable_market(market).family


def _is_proven_bad_roi(
    *,
    sample_size: int,
    roi: float,
    threshold: float,
    min_sample_size: int,
) -> bool:
    return sample_size >= min_sample_size and roi < threshold


def group_predictions(
    session: Session,
    slate: str,
    min_confidence: float = STRICT_GROUPING_MIN_CONFIDENCE,
    min_group_odds: float = PRODUCTION_MIN_GROUP_ODDS,
    require_odds: bool = True,
    use_intelligence_filters: bool = True,
    profile: str | None = None,
    league_odds_filter_mode: str = "strict",
    bankroll: float = DEFAULT_GROUPING_BANKROLL,
) -> dict[str, Any]:

    profile_config = None

    if profile in AUTO_PROFILE_LADDERS:

        for candidate_profile in AUTO_PROFILE_LADDERS[profile]:

            result = group_predictions(
                session=session,
                slate=slate,
                min_confidence=min_confidence,
                min_group_odds=min_group_odds,
                league_odds_filter_mode=league_odds_filter_mode,
                require_odds=require_odds,
                use_intelligence_filters=use_intelligence_filters,
                profile=candidate_profile,
                bankroll=bankroll,
            )

            message = result.get("message")

            if not isinstance(message, dict):

                result["selected_profile"] = {
                    "profile": candidate_profile,
                    "mode": profile,
                }

                return result

        return {
            "message": {
                "status": "no_auto_profile_qualified_groups",
                "profile": profile,
                "reason": (
                    "No approved profile produced "
                    "a strict profitable group."
                ),
            }
        }

    if profile:

        profile_config = PROFILE_CONFIGS.get(profile)

        if profile_config is None:
            raise ValueError(
                f"Unknown profile: {profile}"
            )

        profile_min_confidence = float(
            profile_config["min_confidence"]
        )

        min_confidence = min(
            profile_min_confidence,
            max(
                float(min_confidence),
                STRICT_GROUPING_MIN_CONFIDENCE,
            ),
        )

        _diag(
            "profile_confidence_resolution",
            {
                "profile": profile,
                "profile_min_confidence": (
                    profile_min_confidence
                ),
                "requested_min_confidence": (
                    float(min_confidence)
                ),
                "effective_min_confidence": (
                    min_confidence
                ),
            },
        )

    config = PortfolioGroupConfig(
        min_confidence=max(
            float(min_confidence),
            STRICT_GROUPING_MIN_CONFIDENCE,
        ),
        min_group_odds=max(
            float(min_group_odds),
            PRODUCTION_MIN_GROUP_ODDS,
        ),
        max_group_odds=PRODUCTION_MAX_GROUP_ODDS,
        min_sample_size=10,
        use_intelligence_filters=(
            use_intelligence_filters
        ),
        league_odds_filter_mode=(
            league_odds_filter_mode
        ),
        bankroll=float(bankroll),
        max_odds=(
            min(
                float(
                    profile_config["max_odds"]
                ),
                4.20,
            )
            if profile_config
            else 4.20
        ),
    )

    portfolio_groups = (
        _build_profitability_aware_groups(
            session=session,
            slate=slate,
            config=config,
            require_odds=require_odds,
        )
    )

    if portfolio_groups:

        execution_safe_groups = []

        for group in portfolio_groups:

            safe_group = [
                item
                for item in group
                if (
                    item.get("execution_ready")
                    and not item.get("stale_odds")
                    and float(
                        item.get(
                            "survivability_score"
                        )
                        or 0.0
                    ) >= 0.40
                )
            ]

            if (
                len(safe_group)
                >= config.min_group_size
            ):
                execution_safe_groups.append(
                    safe_group
                )

        _diag(
            "execution_safe_groups",
            len(execution_safe_groups),
        )

        if execution_safe_groups:

            _save_groups(
                session=session,
                slate=slate,
                groups=execution_safe_groups,
            )

            session.commit()

            return _summarize_portfolio_groups(
                groups=execution_safe_groups,
                config=config,
            )

    if profile:
        return {
            "message": {
                "status": (
                    "no_profile_qualified_groups"
                ),
                "profile": profile,
                "reason": (
                    "No picks passed strict "
                    "adaptive profitability filters."
                ),
            }
        }

    return _fallback_confidence_groups(
        session=session,
        slate=slate,
        min_confidence=config.min_confidence,
        min_group_odds=config.min_group_odds,
        max_group_odds=config.max_group_odds,
        require_odds=require_odds,
        league_odds_filter_mode=(
            league_odds_filter_mode
        ),
        bankroll=config.bankroll,
        flat_stake=config.flat_stake,
    )

def _build_profitability_aware_groups(
    session: Session,
    slate: str,
    config: PortfolioGroupConfig,
    require_odds: bool,
) -> list[list[dict[str, Any]]]:
    intelligence_config = IntelligenceConfig(
        min_sample_size=config.min_sample_size,
    )

    market_intel = load_market_intelligence(session, intelligence_config)
    league_market_intel = load_league_market_intelligence(session, intelligence_config)
    odds_band_intel = load_odds_band_intelligence(session, intelligence_config)
    confidence_band_intel = load_confidence_band_intelligence(session, intelligence_config)

    portfolio_context = build_portfolio_filter_context(session=session)
    enabled_markets = portfolio_context.enabled_markets

    if not market_intel:
        _diag("market_intel", "missing_market_intelligence_soft_mode")

    predictions = _load_live_prediction_candidates(
        session=session,
        slate=slate,
        min_confidence=config.min_confidence,
        require_odds=require_odds,
        enabled_markets=enabled_markets,
        max_candidates=MAX_RAW_CANDIDATES,
    )

    _diag("raw_predictions", len(predictions))

    predictions = _prefer_best_odds_candidates(predictions)

    _diag("best_odds_candidates", len(predictions))

    predictions = predictions[:MAX_ENRICHMENT_CANDIDATES]

    _diag("enrichment_candidates", len(predictions))

    predictions, league_rejections = filter_candidate_dicts_by_league_quality(
        session=session,
        candidates=predictions,
        mode=config.league_odds_filter_mode,
    )

    _diag("league_approved", len(predictions))
    _diag("league_rejected", len(league_rejections))

    if league_rejections:
        rejection_summary: dict[str, int] = {}

        for item in league_rejections:
            reason = str(item.get("reason") or "unknown")
            rejection_summary[reason] = rejection_summary.get(reason, 0) + 1

        _diag("league_rejection_breakdown", rejection_summary)

    best_by_match: dict[int, dict[str, Any]] = {}
    enrich_rejections: dict[str, int] = {}

    for prediction in predictions:
        enriched = _enrich_candidate(
            session=session,
            prediction=prediction,
            market_intel=market_intel,
            league_market_intel=league_market_intel,
            odds_band_intel=odds_band_intel,
            confidence_band_intel=confidence_band_intel,
            config=config,
            enabled_markets=enabled_markets,
            portfolio_context=portfolio_context,
        )

        if enriched is None:
            reason = str(prediction.get("_rejection_reason") or "unknown_enrich_rejection")
            enrich_rejections[reason] = enrich_rejections.get(reason, 0) + 1
            continue

        match_id = int(enriched["match_id"])
        current_best = best_by_match.get(match_id)

        if current_best is None or _best_grouping_pick_score(enriched) > _best_grouping_pick_score(current_best):
            best_by_match[match_id] = enriched

    _diag("best_by_match", len(best_by_match))
    _diag("enrich_rejection_breakdown", enrich_rejections)

    enriched_candidates = sorted(
        best_by_match.values(),
        key=lambda item: (
            item.get("portfolio_tier") not in {"SAFE", "MODERATE"},
            float(item.get("portfolio_risk_score") or 999.0),
            -float(item["selection_score"]),
            -float(item.get("odds_match_quality_score") or 0.0),
            -float(item["confidence"]),
            -float(item.get("value_score") or 0.0),
            item["prediction_id"],
        ),
    )[:MAX_UNIQUE_MATCH_CANDIDATES]

    _diag("enriched_candidates", len(enriched_candidates))

    if len(enriched_candidates) < config.min_group_size:
        _diag("failed_stage", "not_enough_enriched_candidates")
        return []

    scored_candidates = score_pick_list(enriched_candidates)

    _diag("scored_candidates", len(scored_candidates))

    exposure_result = apply_exposure_controls(
        picks=scored_candidates,
        max_per_league=config.max_same_league_per_group,
        max_per_market=config.max_same_market_per_group,
        max_per_market_family=config.max_same_family_per_group,
    )

    recommendation_layer = build_recommendation_layer(
        exposure_result=exposure_result,
    )

    approved_source = recommendation_layer.get("approved_picks", [])
    watchlist_source = recommendation_layer.get("watchlist_picks", [])

    recommendation_pool = list(approved_source) + list(watchlist_source)

    if len(recommendation_pool) < config.min_group_size:
        _diag(
            "recommendation_pool_fallback",
            {
                "reason": "recommendation_layer_too_strict_for_grouping",
                "approved": len(approved_source),
                "watchlist": len(watchlist_source),
                "using_scored_candidates": len(scored_candidates),
            },
        )

        recommendation_pool = [
            pick
            for pick in scored_candidates
            if pick.get("risk_level") != "AVOID"
            and not pick.get("exposure_rejected")
        ]
        
    _diag("recommendation_approved_source", len(approved_source))
    _diag("recommendation_watchlist_source", len(watchlist_source))
    _diag("recommendation_pool", len(recommendation_pool))

    approved_candidates: list[dict[str, Any]] = []
    rejection_counts: dict[str, int] = {}

    for pick in recommendation_pool:
        allowed, reason = _strict_adaptive_candidate_allowed(
            pick=pick,
            market_intel=market_intel,
            config=config,
        )

        if not allowed:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            continue

        approved_candidates.append(pick)

    approved_candidates = sorted(
        approved_candidates,
        key=lambda item: (
            item.get("recommendation_status") == "WATCHLIST",
            item.get("portfolio_tier") not in {"SAFE", "MODERATE"},
            float(item.get("portfolio_risk_score") or 999.0),
            -float(item.get("production_score") or 0.0),
            -float(item.get("selection_score") or 0.0),
            -float(item.get("value_score") or 0.0),
            -float(item.get("confidence") or 0.0),
        ),
    )[:MAX_APPROVED_CANDIDATES]

    _diag("approved_candidates", len(approved_candidates))
    _diag("approved_rejection_breakdown", rejection_counts)

    if len(approved_candidates) < config.min_group_size:
        _diag("failed_stage", "not_enough_approved_candidates")
        return []

    groups = _construct_diversified_groups(
        candidates=approved_candidates,
        config=config,
    )

    _diag("groups_constructed", len(groups))

    if not groups:
        _diag("failed_stage", "construct_diversified_groups")

    return groups


def _strict_adaptive_candidate_allowed(
    *,
    pick: dict[str, Any],
    market_intel: dict[str, dict[str, Any]],
    config: PortfolioGroupConfig,
) -> tuple[bool, str]:

    market = str(pick.get("market") or "")
    confidence = _float_value(pick.get("confidence"))
    value_score = _float_value(pick.get("value_score"))
    production_score = _float_value(pick.get("production_score"))
    portfolio_risk_score = _float_value(pick.get("portfolio_risk_score"), 999.0)
    portfolio_tier = str(pick.get("portfolio_tier") or "")
    risk_level = str(pick.get("risk_level") or "")
    odds_match_quality = str(pick.get("odds_match_quality") or "")
    missing_market_intel = (
        bool(pick.get("missing_market_intel"))
        or market not in market_intel
    )

    survivability_score = _float_value(
        pick.get("survivability_score")
    )
    downgrade_risk_score = _float_value(
        pick.get("downgrade_risk_score")
    )
    stale_odds = bool(pick.get("stale_odds"))
    execution_ready = bool(pick.get("execution_ready"))
    survivability_bucket = str(pick.get("survivability_bucket") or "")

    if risk_level == "AVOID":
        return False, "risk_level_avoid"

    if pick.get("exposure_rejected"):
        return False, "exposure_rejected"

    if odds_match_quality != "exact_executable_market":
        return False, "odds_quality"

    if stale_odds:
        return False, "stale_odds"

    if not execution_ready:
        return False, "not_execution_ready"

    if survivability_score < 0.45:
        return False, "low_survivability"

    if survivability_bucket == "WEAK":
        return False, "weak_survivability_bucket"

    if downgrade_risk_score > 0.70:
        return False, "high_downgrade_risk"

    if confidence < config.min_confidence:
        return False, "confidence"

    if value_score < config.min_value_score:
        return False, "value_score"

    if portfolio_tier == "REJECTED":
        return False, "portfolio_rejected"

    if portfolio_risk_score > ADAPTIVE_MAX_PORTFOLIO_RISK:
        return False, "adaptive_risk_score"

    if portfolio_risk_score > STRICT_MAX_PORTFOLIO_RISK:
        if confidence < 0.70 or value_score < 0.10:
            return False, "risk_score_requires_stronger_edge"

    if production_score < STRICT_MIN_PRODUCTION_SCORE:
        if missing_market_intel:
            if (
                confidence < IMMATURE_INTELLIGENCE_CONFIDENCE_FLOOR
                or value_score < IMMATURE_INTELLIGENCE_VALUE_FLOOR
            ):
                return False, "immature_market_low_strength"
        else:
            if confidence < 0.66 or value_score < 0.08:
                return False, "production_score_low"

    if missing_market_intel:
        if confidence < IMMATURE_INTELLIGENCE_CONFIDENCE_FLOOR:
            return False, "missing_market_intel_confidence"

        if value_score < IMMATURE_INTELLIGENCE_VALUE_FLOOR:
            return False, "missing_market_intel_value"

    return True, "approved"

def _load_live_prediction_candidates(
    session: Session,
    slate: str,
    min_confidence: float,
    require_odds: bool,
    enabled_markets: set[str],
    max_candidates: int,
) -> list[dict[str, Any]]:

    if not enabled_markets:
        return []

    odds_filter = (
        "AND p.odds IS NOT NULL"
        if require_odds
        else ""
    )

    query = text(
        f"""
        SELECT
            p.id AS prediction_id,
            p.slate,
            p.match_id,
            p.market,
            p.predicted_label,
            p.confidence,
            p.odds,
            p.implied_probability,
            p.value_score,
            p.odds_bookmaker,
            p.odds_market,
            p.odds_selection,
            p.odds_retrieved_at,
            p.odds_match_quality,
            p.model_name,
            p.sport,

            p.execution_market,
            p.execution_selection,
            p.execution_family,
            p.execution_line,
            p.bookmaker_locality,
            p.local_realism_score,
            p.execution_score,
            p.survivability_score,
            p.execution_ready,
            p.execution_reasons,
            p.market_alternatives,

            m.league,
            m.home_team,
            m.away_team,
            m.kickoff_date,
            m.kickoff_datetime,

            m.status,
            m.is_finished,
            m.is_postponed,
            m.is_cancelled

        FROM predictions p
        JOIN matches m
            ON m.id = p.match_id

        WHERE p.slate = :slate
          AND p.confidence >= :min_confidence
          AND p.market = ANY(:enabled_markets)
          AND p.value_score IS NOT NULL
          AND p.value_score >= :min_value_score
          AND p.odds_match_quality = 'exact_executable_market'
          AND p.odds_bookmaker IS NOT NULL
          {odds_filter}

        ORDER BY
            p.execution_ready DESC NULLS LAST,
            p.execution_score DESC NULLS LAST,
            p.survivability_score DESC NULLS LAST,
            p.local_realism_score DESC NULLS LAST,
            p.value_score DESC NULLS LAST,
            p.confidence DESC,
            p.odds ASC NULLS LAST,
            p.id ASC

        LIMIT :max_candidates
        """
    )

    rows = session.execute(
        query,
        {
            "slate": slate,
            "min_confidence": float(min_confidence),
            "min_value_score": STRICT_GROUPING_MIN_VALUE_SCORE,
            "enabled_markets": list(enabled_markets),
            "max_candidates": int(max_candidates),
        },
    ).fetchall()

    raw_candidates = [
        dict(row._mapping)
        for row in rows
    ]

    candidates: list[dict[str, Any]] = []

    blocked_statuses = {
        "FT",
        "AET",
        "PEN",
        "LIVE",
        "1H",
        "2H",
        "HT",
        "BREAK",
        "INT",
        "PST",
        "CANC",
        "ABD",
    }

    for candidate in raw_candidates:

        if candidate.get("is_finished"):
            continue

        if candidate.get("is_postponed"):
            continue

        if candidate.get("is_cancelled"):
            continue

        status = str(
            candidate.get("status") or ""
        ).upper()

        if status in blocked_statuses:
            continue

        if require_odds and candidate.get("odds") is None:
            continue

        candidate["kickoff_time"] = (
            _candidate_kickoff_time(candidate)
        )

        candidate["execution_ready"] = bool(
            candidate.get("execution_ready")
        )

        candidate["execution_score"] = _float_value(
            candidate.get("execution_score")
        )

        candidate["survivability_score"] = _float_value(
            candidate.get("survivability_score")
        )

        candidate["local_realism_score"] = _float_value(
            candidate.get("local_realism_score")
        )

        candidates.append(candidate)

    return candidates

def _prefer_best_odds_candidates(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    best: dict[tuple[int, str, str], dict[str, Any]] = {}

    for prediction in predictions:

        key = (
            int(prediction["match_id"]),
            str(prediction["market"]),
            str(
                prediction.get("odds_selection")
                or prediction.get("predicted_label")
            ),
        )

        current = best.get(key)

        if (
            current is None
            or _best_odds_quality_score(prediction)
            > _best_odds_quality_score(current)
        ):
            best[key] = prediction

    return sorted(
        best.values(),
        key=lambda item: (
            bool(item.get("stale_odds")),
            -float(item.get("survivability_score") or 0.0),
            -_best_odds_quality_score(item),
            -float(item.get("value_score") or 0.0),
            -float(item.get("confidence") or 0.0),
            float(item.get("odds") or 999.0),
            int(item["prediction_id"]),
        ),
    )

def _best_odds_quality_score(
    prediction: dict[str, Any],
) -> float:

    quality = (
        prediction.get("odds_match_quality")
        or "none"
    )

    odds = prediction.get("odds")

    value_score = _float_value(
        prediction.get("value_score")
    )

    confidence = _float_value(
        prediction.get("confidence")
    )

    survivability_score = _float_value(
        prediction.get("survivability_score")
    )

    freshness_score = _float_value(
        prediction.get("freshness_score")
    )

    downgrade_risk_score = _float_value(
        prediction.get("downgrade_risk_score")
    )

    execution_score = _float_value(
        prediction.get("execution_score")
    )

    local_realism_score = _float_value(
        prediction.get("local_realism_score")
    )

    bookmaker_locality = str(
        prediction.get("bookmaker_locality") or ""
    ).upper()

    quality_points = {
        "exact_executable_market": 130.0,
        "exact_canonical": 92.0,
        "asian_handicap_family_fallback": 78.0,
        "execution_family_fallback": 68.0,
        "exact_market_fallback": 62.0,
        "direct": 55.0,
    }.get(str(quality), 10.0)

    odds_points = 0.0

    if odds is not None:

        selected_odds = float(odds)

        if 1.35 <= selected_odds <= 2.20:
            odds_points += 18.0

        elif 2.20 < selected_odds <= 3.00:
            odds_points += 9.0

        elif 3.00 < selected_odds <= 4.20:
            odds_points -= 6.0

        elif selected_odds > 4.20:
            odds_points -= 38.0

        elif selected_odds < 1.30:
            odds_points -= 42.0

        if selected_odds >= 4.00:
            odds_points -= 22.0

    bookmaker_points = (
        12.0
        if prediction.get("odds_bookmaker")
        else -28.0
    )

    local_bookmaker_bonus = (
        14.0
        if bookmaker_locality == "LOCAL"
        else 0.0
    )

    inversion_points = (
        3.0
        if _is_not_inversion_label(
            prediction.get("predicted_label")
        )
        else 0.0
    )

    survivability_points = (
        survivability_score * 28.0
    )

    freshness_points = (
        freshness_score * 12.0
    )

    execution_points = min(
        execution_score * 0.45,
        70.0,
    )

    local_realism_points = (
        local_realism_score * 26.0
    )

    downgrade_penalty = (
        downgrade_risk_score * 30.0
    )

    stale_penalty = (
        38.0
        if prediction.get("stale_odds")
        else 0.0
    )

    execution_bonus = (
        14.0
        if prediction.get("execution_ready")
        else -22.0
    )

    return round(
        quality_points
        + bookmaker_points
        + local_bookmaker_bonus
        + inversion_points
        + survivability_points
        + freshness_points
        + execution_points
        + local_realism_points
        + execution_bonus
        + min(value_score * 125.0, 30.0)
        + min(confidence * 14.0, 14.0)
        + odds_points
        - downgrade_penalty
        - stale_penalty,
        4,
    )

def _best_grouping_pick_score(
    prediction: dict[str, Any],
) -> float:

    portfolio_risk = _float_value(
        prediction.get("portfolio_risk_score"),
        0.0,
    )

    immature_penalty = _float_value(
        prediction.get("sample_penalty"),
        0.0,
    )

    production_score = _float_value(
        prediction.get("production_score"),
        0.0,
    )

    survivability_score = _float_value(
        prediction.get("survivability_score"),
        0.0,
    )

    downgrade_risk_score = _float_value(
        prediction.get("downgrade_risk_score"),
        0.0,
    )

    execution_score = _float_value(
        prediction.get("execution_score"),
        0.0,
    )

    local_realism_score = _float_value(
        prediction.get("local_realism_score"),
        0.0,
    )

    stale_penalty = (
        0.22 if prediction.get("stale_odds") else 0.0
    )

    execution_bonus = (
        0.12 if prediction.get("execution_ready") else -0.18
    )

    local_bonus = (
        0.05
        if str(prediction.get("bookmaker_locality") or "").upper() == "LOCAL"
        else 0.0
    )

    return round(
        float(prediction.get("selection_score") or 0.0)
        + (_best_odds_quality_score(prediction) / 750.0)
        + (production_score / 1100.0)
        + (survivability_score * 0.20)
        + (execution_score / 900.0)
        + (local_realism_score * 0.12)
        + execution_bonus
        + local_bonus
        - (downgrade_risk_score * 0.14)
        - stale_penalty
        - (portfolio_risk / 560.0)
        - immature_penalty,
        6,
    )

def _enrich_candidate(
    session: Session,
    prediction: dict[str, Any],
    market_intel: dict[str, dict[str, Any]],
    league_market_intel: dict[tuple[str, str], dict[str, Any]],
    odds_band_intel: dict[tuple[str, str], dict[str, Any]],
    confidence_band_intel: dict[tuple[str, str], dict[str, Any]],
    config: PortfolioGroupConfig,
    enabled_markets: set[str],
    portfolio_context: PortfolioFilterContext,
) -> dict[str, Any] | None:

    market = prediction["market"]

    league = prediction.get("league") or "unknown"

    executable = parse_executable_market(
        market
    )

    if (
        executable.family == "ASIAN_HANDICAP"
        and prediction.get("odds") is not None
        and float(prediction["odds"]) >= 3.50
    ):
        prediction["_rejection_reason"] = (
            "unstable_high_odds_handicap"
        )
        return None

    if executable.volatility_tier == "EXTREME":
        prediction["_rejection_reason"] = (
            "extreme_volatility"
        )
        return None

    if executable.family in {
        "EXACT_SCORE",
        "HT_FT",
    }:
        prediction["_rejection_reason"] = (
            "blocked_derivative_family"
        )
        return None

    if market not in enabled_markets:
        prediction["_rejection_reason"] = (
            "market_disabled"
        )
        return None

    confidence = float(
        prediction["confidence"] or 0.0
    )

    value_score = float(
        prediction["value_score"] or 0.0
    )

    odds = prediction.get("odds")

    if odds is None:
        prediction["_rejection_reason"] = (
            "missing_odds"
        )
        return None

    odds = float(odds)

    timing = analyze_prediction_timing(
        kickoff_value=(
            prediction.get("kickoff_datetime")
            or prediction.get("kickoff_date")
        )
    )

    prediction["kickoff_time"] = (
        timing.kickoff_eat
    )

    prediction["minutes_to_kickoff"] = (
        timing.minutes_to_kickoff
    )

    prediction["timing_status"] = (
        timing.timing_status
    )

    prediction["recommended_action"] = (
        timing.recommended_action
    )

    prediction["timing_reason"] = (
        timing.reason
    )

    if (
        timing.minutes_to_kickoff is not None
        and timing.minutes_to_kickoff <= 8
    ):
        prediction["_rejection_reason"] = (
            "too_close_to_kickoff"
        )
        return None

    if (
        executable.family == "ASIAN_HANDICAP"
        and timing.minutes_to_kickoff is not None
        and timing.minutes_to_kickoff <= 35
    ):
        prediction["_rejection_reason"] = (
            "late_asian_handicap_window"
        )
        return None

    if timing.recommended_action == "AVOID":
        prediction["_rejection_reason"] = (
            f"timing_{timing.timing_status}"
        )
        return None

    survivability = evaluate_odds_survivability(
        market=market,
        bookmaker=prediction.get(
            "odds_bookmaker"
        ),
        odds_retrieved_at=prediction.get(
            "odds_retrieved_at"
        ),
        minutes_to_kickoff=(
            timing.minutes_to_kickoff
        ),
    )

    prediction["survivability_score"] = (
        survivability.survivability_score
    )

    prediction["freshness_score"] = (
        survivability.freshness_score
    )

    prediction["persistence_score"] = (
        survivability.persistence_score
    )

    prediction["downgrade_risk_score"] = (
        survivability.downgrade_risk_score
    )

    prediction["fallback_markets"] = (
        survivability.fallback_markets
    )

    prediction["primary_fallback_market"] = (
        survivability.fallback_markets[0]
        if survivability.fallback_markets
        else None
    )

    prediction["survivability_reasons"] = (
        survivability.reasons
    )

    prediction["stale_odds"] = (
        survivability.stale
    )

    prediction["survivability_bucket"] = (
        "ELITE"
        if survivability.survivability_score >= 0.80
        else (
            "STRONG"
            if survivability.survivability_score >= 0.65
            else (
                "MODERATE"
                if survivability.survivability_score >= 0.50
                else "WEAK"
            )
        )
    )

    if not survivability.allowed:
        prediction["_rejection_reason"] = (
            "poor_survivability"
        )
        return None

    if confidence < config.min_confidence:
        prediction["_rejection_reason"] = (
            "confidence"
        )
        return None

    if value_score < config.min_value_score:
        prediction["_rejection_reason"] = (
            "value_score"
        )
        return None

    if odds < config.min_odds or odds > config.max_odds:
        prediction["_rejection_reason"] = (
            "odds_range"
        )
        return None

    if (
        prediction.get("odds_match_quality")
        != "exact_executable_market"
    ):
        prediction["_rejection_reason"] = (
            "odds_quality"
        )
        return None

    if not prediction.get("odds_bookmaker"):
        prediction["_rejection_reason"] = (
            "missing_bookmaker"
        )
        return None

    missing_market_intel = (
        market not in market_intel
    )

    if missing_market_intel:

        if (
            confidence
            < IMMATURE_INTELLIGENCE_CONFIDENCE_FLOOR
        ):
            prediction["_rejection_reason"] = (
                "missing_market_intel_confidence"
            )
            return None

        if (
            value_score
            < IMMATURE_INTELLIGENCE_VALUE_FLOOR
        ):
            prediction["_rejection_reason"] = (
                "missing_market_intel_value"
            )
            return None

    if config.use_intelligence_filters:

        filter_result = evaluate_pick_for_portfolio(
            session=None,
            context=portfolio_context,
            league=league,
            market=market,
            confidence=confidence,
            odds=odds,
            value_score=value_score,
            strict=False,
        )

        if not filter_result.allowed:
            prediction["_rejection_reason"] = (
                f"portfolio_{filter_result.reason}"
            )
            return None

        prediction["portfolio_allowed"] = (
            filter_result.allowed
        )

        prediction["portfolio_filter_reason"] = (
            filter_result.reason
        )

        prediction["portfolio_risk_flags"] = (
            filter_result.risk_flags
        )

        prediction["portfolio_risk_score"] = (
            filter_result.risk_score
        )

        prediction["portfolio_tier"] = (
            filter_result.tier
        )

    else:

        prediction["portfolio_allowed"] = True
        prediction["portfolio_filter_reason"] = (
            "Not used"
        )
        prediction["portfolio_risk_flags"] = []
        prediction["portfolio_risk_score"] = 0.0
        prediction["portfolio_tier"] = "UNFILTERED"

    if prediction["portfolio_tier"] == "REJECTED":
        prediction["_rejection_reason"] = (
            "portfolio_rejected"
        )
        return None

    if (
        float(
            prediction["portfolio_risk_score"]
        )
        > ADAPTIVE_MAX_PORTFOLIO_RISK
    ):
        prediction["_rejection_reason"] = (
            "adaptive_max_risk"
        )
        return None

    if (
        float(
            prediction["portfolio_risk_score"]
        )
        > STRICT_MAX_PORTFOLIO_RISK
    ):
        if confidence < 0.70 or value_score < 0.10:
            prediction["_rejection_reason"] = (
                "risk_requires_stronger_edge"
            )
            return None

    market_data = market_intel.get(
        market,
        {
            "roi": 0.0,
            "hit_rate": 0.0,
            "sample_size": 0,
        },
    )

    league_data = league_market_intel.get(
        (league, market)
    )

    odds_data = odds_band_intel.get(
        (market, odds_band(odds))
    )

    confidence_data = confidence_band_intel.get(
        (
            market,
            confidence_band(confidence),
        )
    )

    market_roi = float(
        market_data.get("roi") or 0.0
    )

    league_roi = (
        float(league_data.get("roi") or 0.0)
        if league_data
        else 0.0
    )

    odds_band_roi = (
        float(odds_data.get("roi") or 0.0)
        if odds_data
        else 0.0
    )

    confidence_band_roi = (
        float(
            confidence_data.get("roi") or 0.0
        )
        if confidence_data
        else 0.0
    )

    sample_penalty = _sample_penalty(
        market_sample_size=int(
            market_data.get("sample_size") or 0
        ),
        league_sample_size=int(
            league_data.get("sample_size") or 0
        )
        if league_data
        else 0,
        odds_band_sample_size=int(
            odds_data.get("sample_size") or 0
        )
        if odds_data
        else 0,
        confidence_band_sample_size=int(
            confidence_data.get("sample_size")
            or 0
        )
        if confidence_data
        else 0,
        min_sample_size=config.min_sample_size,
        missing_market_intel=missing_market_intel,
    )

    odds_quality = _odds_quality_component(
        odds
    )

    risk_penalty = (
        max(
            float(
                prediction.get(
                    "portfolio_risk_score"
                ) or 0.0
            ),
            0.0,
        )
        / 110.0
    )

    odds_match_quality_score = (
        _best_odds_quality_score(
            prediction
        )
    )

    execution_score = _float_value(
        prediction.get("execution_score")
    )

    local_realism_score = _float_value(
        prediction.get("local_realism_score")
    )

    bookmaker_locality = str(
        prediction.get("bookmaker_locality") or ""
    ).upper()

    bookmaker_execution_score = (
        odds_match_quality_score / 100.0
    )

    execution_quality_boost = min(
        execution_score / 140.0,
        1.0,
    )

    local_realism_boost = (
        local_realism_score * 0.16
    )

    local_bookmaker_boost = (
        0.05
        if bookmaker_locality == "LOCAL"
        else 0.0
    )

    execution_risk_penalty = (
        float(
            prediction.get(
                "downgrade_risk_score"
            ) or 0.0
        )
        * 0.12
    )
    if executable.execution_risk == "HIGH":
        execution_risk_penalty += 0.04

    if executable.volatility_tier == "HIGH":
        execution_risk_penalty += 0.035

    if prediction.get("stale_odds"):
        execution_risk_penalty += 0.08

    if (
        prediction.get(
            "survivability_bucket"
        ) == "WEAK"
    ):
        execution_risk_penalty += 0.10

    elif (
        prediction.get(
            "survivability_bucket"
        ) == "MODERATE"
    ):
        execution_risk_penalty += 0.04

    selection_score = (
        confidence * 0.27
        + float(
            prediction[
                "survivability_score"
            ]
        )
        * 0.15
        + value_score * 0.31
        + market_roi * 0.09
        + league_roi * 0.07
        + odds_band_roi * 0.05
        + confidence_band_roi * 0.05
        + odds_quality * 0.07
        + bookmaker_execution_score * 0.10
        + execution_quality_boost * 0.09
        + local_realism_boost
        + local_bookmaker_boost
        - sample_penalty
        - risk_penalty
        - execution_risk_penalty
    )
    prediction["kickoff_time"] = (
        _candidate_kickoff_time(
            prediction
        )
    )

    prediction["market_family"] = (
        executable.family
    )

    prediction["executable_label"] = (
        _render_executable_label(
            prediction
        )
    )

    prediction["selection_score"] = (
        selection_score
    )

    prediction["execution_ready"] = (
        prediction.get(
            "survivability_bucket"
        )
        in {"ELITE", "STRONG"}
        and not prediction.get("stale_odds")
    )

    return prediction

def _odds_quality_component(odds: float) -> float:
    if odds < 1.30:
        return -0.50
    if odds <= 1.80:
        return 0.35
    if odds <= 2.50:
        return 0.50
    if odds <= 3.20:
        return 0.25
    if odds <= 4.20:
        return -0.05
    return -0.60


def _sample_penalty(
    market_sample_size: int,
    league_sample_size: int,
    odds_band_sample_size: int,
    confidence_band_sample_size: int,
    min_sample_size: int,
    missing_market_intel: bool = False,
) -> float:
    penalty = 0.0

    if missing_market_intel:
        penalty += 0.04
    elif market_sample_size < min_sample_size:
        penalty += 0.035
    elif market_sample_size < min_sample_size * 2:
        penalty += 0.02

    if league_sample_size == 0:
        penalty += 0.035
    elif league_sample_size < min_sample_size:
        penalty += 0.025

    if odds_band_sample_size == 0:
        penalty += 0.025
    elif odds_band_sample_size < min_sample_size:
        penalty += 0.015

    if confidence_band_sample_size == 0:
        penalty += 0.025
    elif confidence_band_sample_size < min_sample_size:
        penalty += 0.015

    return penalty


def _construct_diversified_groups(
    candidates: list[dict[str, Any]],
    config: PortfolioGroupConfig,
) -> list[list[dict[str, Any]]]:

    groups: list[list[dict[str, Any]]] = []

    used_match_ids: set[int] = set()

    candidates = sorted(
        candidates,
        key=lambda item: (
            item.get("recommendation_status") == "WATCHLIST",
            float(item.get("portfolio_risk_score") or 999.0),
            -float(item.get("selection_score") or 0.0),
            -float(item.get("production_score") or 0.0),
            -float(item.get("confidence") or 0.0),
            -float(item.get("value_score") or 0.0),
        ),
    )

    for _ in range(config.max_groups):

        group: list[dict[str, Any]] = []

        for candidate in candidates:

            match_id = int(candidate["match_id"])

            if match_id in used_match_ids:
                continue

            if not _candidate_fits_group(
                candidate,
                group,
                config,
            ):
                continue

            test_group = group + [candidate]

            if not _group_odds_within_limits(
                group=test_group,
                min_group_odds=0.0,
                max_group_odds=config.max_group_odds,
            ):
                continue

            group.append(candidate)

            used_match_ids.add(match_id)

            if len(group) >= config.max_group_size:
                break

        validation = validate_group_for_execution(
            group=group
        )

        if (
            len(group) >= config.min_group_size
            and validation["allowed"]
            and _group_odds_within_limits(
                group=validation["approved_picks"],
                min_group_odds=config.min_group_odds,
                max_group_odds=config.max_group_odds,
            )
        ):

            groups.append(
                validation["approved_picks"]
            )

        else:

            for item in group:
                used_match_ids.discard(
                    int(item["match_id"])
                )

            break

    return groups

def _group_odds_within_limits(
    group: list[dict[str, Any]],
    min_group_odds: float,
    max_group_odds: float,
) -> bool:

    odds_values = [
        float(item["odds"])
        for item in group
        if item.get("odds") is not None
    ]

    if len(odds_values) != len(group):
        return False

    survivability_scores = [
        float(
            item.get(
                "survivability_score"
            ) or 0.0
        )
        for item in group
    ]

    stale_count = sum(
        1
        for item in group
        if item.get("stale_odds")
    )

    execution_ready_count = sum(
        1
        for item in group
        if item.get("execution_ready")
    )

    cumulative = float(prod(odds_values))

    if cumulative <= 1.0:
        return False

    if (
        cumulative < min_group_odds
        or cumulative > max_group_odds
    ):
        return False

    average_survivability = (
        mean(survivability_scores)
        if survivability_scores
        else 0.0
    )

    if average_survivability < 0.45:
        return False

    if stale_count >= 1:
        return False

    if execution_ready_count < len(group):
        return False

    for item in group:

        odds = float(
            item.get("odds") or 0.0
        )

        market = str(
            item.get("market") or ""
        )

        executable = parse_executable_market(
            market
        )

        if odds >= 4.00:
            return False

        if (
            executable.family
            == "ASIAN_HANDICAP"
            and odds >= 3.20
        ):
            return False

        if (
            executable.volatility_tier
            == "EXTREME"
        ):
            return False

    return True

def _candidate_fits_group(
    candidate: dict[str, Any],
    group: list[dict[str, Any]],
    config: PortfolioGroupConfig,
) -> bool:

    market = candidate["market"]
    league = candidate.get("league") or "unknown"
    market_family = (
        candidate.get("market_family")
        or _resolve_group_market_family(market)
    )

    if candidate.get("stale_odds"):
        return False

    if not candidate.get("execution_ready"):
        return False

    if float(candidate.get("survivability_score") or 0.0) < 0.45:
        return False

    conflict = evaluate_prediction_conflict(
        candidate=candidate,
        existing_predictions=group,
    )

    candidate["conflict_score"] = conflict.get(
        "conflict_score",
        0.0,
    )
    candidate["conflict_level"] = conflict.get(
        "conflict_level",
        "NONE",
    )
    candidate["conflict_reasons"] = conflict.get(
        "reasons",
        [],
    )

    if not conflict.get("allowed", True):
        return False

    same_market_count = sum(
        1 for item in group if item["market"] == market
    )

    same_league_count = sum(
        1
        for item in group
        if (item.get("league") or "unknown") == league
    )

    same_family_count = sum(
        1
        for item in group
        if (
            item.get("market_family")
            or _resolve_group_market_family(item["market"])
        ) == market_family
    )

    if same_market_count >= config.max_same_market_per_group:
        return False

    if same_league_count >= config.max_same_league_per_group:
        return False

    if same_family_count >= config.max_same_family_per_group:
        return False

    if market_family == "ASIAN_HANDICAP":
        existing_handicap_count = sum(
            1
            for item in group
            if (
                item.get("market_family")
                or _resolve_group_market_family(item["market"])
            ) == "ASIAN_HANDICAP"
        )

        if existing_handicap_count >= 1:
            return False

    if not group:
        candidate["market_family"] = market_family
        candidate["correlation_score"] = 0.0
        candidate["correlation_reasons"] = []
        return True

    correlation = evaluate_group_correlation(
        existing_group=group,
        candidate=candidate,
    )

    candidate["correlation_score"] = correlation.correlation_score
    candidate["correlation_reasons"] = correlation.reasons

    if not correlation.allowed:
        return False

    candidate["market_family"] = market_family
    return True

def _save_groups(
    session: Session,
    slate: str,
    groups: list[list[dict[str, Any]]],
) -> None:

    session.execute(
        delete(PredictionGroupItem).where(
            PredictionGroupItem.slate == slate,
        )
    )

    for group_index, group in enumerate(
        groups,
        start=1,
    ):

        valid_group = [
            item
            for item in group
            if (
                item.get("execution_ready")
                and not item.get("stale_odds")
            )
        ]

        if len(valid_group) < 2:
            continue

        group_name = (
            f"Portfolio Group {group_index}"
        )

        for item in valid_group:

            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=int(
                        item["prediction_id"]
                    ),
                )
            )

def _summarize_portfolio_groups(
    groups: list[list[dict[str, Any]]],
    config: PortfolioGroupConfig,
) -> dict[str, Any]:

    summaries: dict[str, Any] = {}

    daily_exposure_used = 0.0

    for group_index, group in enumerate(
        groups,
        start=1,
    ):

        group_name = (
            f"Portfolio Group {group_index}"
        )

        odds_values = [
            float(item["odds"])
            for item in group
            if item.get("odds") is not None
        ]

        confidence_values = [
            float(item.get("confidence") or 0.0)
            for item in group
        ]

        risk_scores = [
            float(item.get("portfolio_risk_score") or 0.0)
            for item in group
        ]

        survivability_scores = [
            float(item.get("survivability_score") or 0.0)
            for item in group
        ]

        freshness_scores = [
            float(item.get("freshness_score") or 0.0)
            for item in group
        ]

        average_risk_score = mean(risk_scores) if risk_scores else 0.0
        max_risk_score = max(risk_scores) if risk_scores else 0.0
        average_survivability = mean(survivability_scores) if survivability_scores else 0.0
        average_freshness = mean(freshness_scores) if freshness_scores else 0.0

        group_tier = resolve_group_tier(
            average_risk_score=average_risk_score,
            max_risk_score=max_risk_score,
            rejected_picks=0,
        )

        cumulative_odds = (
            float(prod(odds_values))
            if len(odds_values) == len(group)
            else 0.0
        )

        stale_count = sum(1 for item in group if item.get("stale_odds"))
        execution_ready_count = sum(1 for item in group if item.get("execution_ready"))

        if cumulative_odds > config.max_group_odds:
            group_tier = "REJECTED"

        if average_survivability < 0.45:
            group_tier = "REJECTED"

        if stale_count >= 2:
            group_tier = "REJECTED"

        stake_decision = calculate_group_stake(
            bankroll=config.bankroll,
            odds_values=odds_values,
            confidence_values=confidence_values,
            tier=group_tier,
            flat_stake=config.flat_stake,
            daily_exposure_used=daily_exposure_used,
        )

        daily_exposure_used += stake_decision.stake

        group_matches = []

        for item in group:

            timing = analyze_prediction_timing(
                kickoff_value=(
                    item.get("kickoff_datetime")
                    or item.get("kickoff_date")
                )
            )

            group_matches.append(
                {
                    "match_id": item.get("match_id"),
                    "league": item.get("league"),
                    "home_team": item.get("home_team"),
                    "away_team": item.get("away_team"),
                    "kickoff_time": timing.kickoff_eat,
                    "minutes_to_kickoff": timing.minutes_to_kickoff,
                    "timing_status": timing.timing_status,
                    "recommended_action": timing.recommended_action,
                    "timing_reason": timing.reason,

                    "market": item.get("market"),
                    "market_family": item.get("market_family"),
                    "predicted_label": item.get("predicted_label"),
                    "executable_label": (
                        item.get("executable_label")
                        or _render_executable_label(item)
                    ),
                    "is_inversion_pick": item.get("is_inversion_pick"),

                    "odds": item.get("odds"),
                    "confidence": item.get("confidence"),
                    "value_score": item.get("value_score"),

                    "bookmaker": item.get("odds_bookmaker"),
                    "odds_market": item.get("odds_market"),
                    "odds_selection": item.get("odds_selection"),
                    "odds_match_quality": item.get("odds_match_quality"),

                    "execution_market": item.get("execution_market"),
                    "execution_selection": item.get("execution_selection"),
                    "execution_family": item.get("execution_family"),
                    "execution_line": item.get("execution_line"),
                    "bookmaker_locality": item.get("bookmaker_locality"),
                    "local_realism_score": item.get("local_realism_score"),
                    "execution_score": item.get("execution_score"),
                    "execution_reasons": item.get("execution_reasons"),
                    "market_alternatives": item.get("market_alternatives"),

                    "conflict_score": item.get("conflict_score"),
                    "conflict_level": item.get("conflict_level"),
                    "conflict_reasons": item.get("conflict_reasons"),

                    "portfolio_tier": item.get("portfolio_tier"),
                    "portfolio_risk_score": item.get("portfolio_risk_score"),
                    "production_score": item.get("production_score"),
                    "pick_grade": item.get("pick_grade"),
                    "risk_level": item.get("risk_level"),
                    "missing_market_intel": item.get("missing_market_intel"),

                    "survivability_score": item.get("survivability_score"),
                    "survivability_bucket": item.get("survivability_bucket"),
                    "freshness_score": item.get("freshness_score"),
                    "persistence_score": item.get("persistence_score"),
                    "downgrade_risk_score": item.get("downgrade_risk_score"),
                    "fallback_markets": item.get("fallback_markets"),
                    "primary_fallback_market": item.get("primary_fallback_market"),
                    "stale_odds": item.get("stale_odds"),
                    "execution_ready": item.get("execution_ready"),
                    "survivability_reasons": item.get("survivability_reasons"),
                }
            )

        summaries[group_name] = {
            "group_type": "STRICT_ADAPTIVE_INTELLIGENCE_PORTFOLIO",
            "group_tier": group_tier,
            "games": float(len(group)),

            "average_confidence": round(
                mean(confidence_values) if confidence_values else 0.0,
                4,
            ),
            "average_value_score": round(
                mean(float(item.get("value_score") or 0.0) for item in group),
                4,
            ),
            "average_market_roi": round(
                mean(float(item.get("market_roi") or 0.0) for item in group),
                4,
            ),
            "average_league_roi": round(
                mean(float(item.get("league_roi") or 0.0) for item in group),
                4,
            ),
            "average_odds_band_roi": round(
                mean(float(item.get("odds_band_roi") or 0.0) for item in group),
                4,
            ),
            "average_confidence_band_roi": round(
                mean(float(item.get("confidence_band_roi") or 0.0) for item in group),
                4,
            ),
            "average_selection_score": round(
                mean(float(item.get("selection_score") or 0.0) for item in group),
                4,
            ),
            "average_survivability_score": round(average_survivability, 4),
            "average_freshness_score": round(average_freshness, 4),
            "stale_pick_count": stale_count,
            "execution_ready_count": execution_ready_count,
            "average_odds_quality_score": round(
                mean(float(item.get("odds_match_quality_score") or 0.0) for item in group),
                4,
            ),
            "average_sample_penalty": round(
                mean(float(item.get("sample_penalty") or 0.0) for item in group),
                4,
            ),
            "average_risk_score": round(average_risk_score, 4),
            "max_risk_score": round(max_risk_score, 4),

            "risk_flags": ", ".join(
                sorted(
                    {
                        flag
                        for item in group
                        for flag in item.get("portfolio_risk_flags", [])
                    }
                )
            ),

            "cumulative_odds": round(cumulative_odds, 4),
            "min_group_odds": round(config.min_group_odds, 4),
            "max_group_odds": round(config.max_group_odds, 4),
            "odds_coverage": round(len(odds_values) / len(group), 4),

            "recommended_stake": stake_decision.stake,
            "stake_method": stake_decision.method,
            "stake_reason": stake_decision.reason,
            "bankroll_pct": stake_decision.bankroll_pct,
            "raw_kelly_fraction": stake_decision.raw_kelly_fraction,
            "applied_fraction": stake_decision.applied_fraction,
            "estimated_group_probability": stake_decision.estimated_probability,
            "expected_value": stake_decision.expected_value,

            "group_matches": group_matches,
        }

    return summaries

def _fallback_confidence_groups(
    session: Session,
    slate: str,
    min_confidence: float = STRICT_GROUPING_MIN_CONFIDENCE,
    min_group_odds: float = PRODUCTION_MIN_GROUP_ODDS,
    max_group_odds: float = PRODUCTION_MAX_GROUP_ODDS,
    require_odds: bool = True,
    league_odds_filter_mode: str = "strict",
    bankroll: float = DEFAULT_GROUPING_BANKROLL,
    flat_stake: float = DEFAULT_FLAT_STAKE,
) -> dict[str, Any]:

    enabled_markets = set(
        get_enabled_markets(session)
    )

    query = (
        select(Prediction)
        .where(
            Prediction.slate == slate,
            Prediction.confidence >= max(
                min_confidence,
                STRICT_GROUPING_MIN_CONFIDENCE,
            ),
            Prediction.market.in_(
                enabled_markets
            ),
            Prediction.value_score.isnot(None),
            Prediction.value_score
            >= STRICT_GROUPING_MIN_VALUE_SCORE,
            Prediction.odds_match_quality
            == "exact_executable_market",
            Prediction.odds_bookmaker.isnot(None),
        )
        .order_by(
            Prediction.value_score.desc(),
            Prediction.confidence.desc(),
            Prediction.id.asc(),
        )
        .limit(MAX_RAW_CANDIDATES)
    )

    if require_odds:

        query = query.where(
            Prediction.odds.isnot(None),
            Prediction.odds >= 1.30,
            Prediction.odds <= 4.20,
        )

    predictions = list(
        session.scalars(query)
    )

    candidate_dicts = [
        {
            "prediction_id": prediction.id,
            "match_id": prediction.match_id,

            "league": None,
            "home_team": None,
            "away_team": None,
            "kickoff_time": None,

            "market": prediction.market,
            "predicted_label": (
                prediction.predicted_label
            ),

            "sport": prediction.sport,
            "prediction": prediction,

            "confidence": prediction.confidence,
            "odds": prediction.odds,
            "value_score": (
                prediction.value_score
            ),

            "odds_bookmaker": (
                prediction.odds_bookmaker
            ),
            "odds_market": (
                prediction.odds_market
            ),
            "odds_selection": (
                prediction.odds_selection
            ),
            "odds_retrieved_at": (
                prediction.odds_retrieved_at
            ),
            "odds_match_quality": (
                prediction.odds_match_quality
            ),

            "execution_market": (
                prediction.execution_market
            ),
            "execution_selection": (
                prediction.execution_selection
            ),
            "execution_family": (
                prediction.execution_family
            ),
            "execution_line": (
                prediction.execution_line
            ),

            "bookmaker_locality": (
                prediction.bookmaker_locality
            ),

            "local_realism_score": (
                prediction.local_realism_score
            ),

            "execution_score": (
                prediction.execution_score
            ),

            "survivability_score": (
                prediction.survivability_score
            ),

            "execution_ready": (
                prediction.execution_ready
            ),

            "execution_reasons": (
                prediction.execution_reasons
                or []
            ),

            "market_alternatives": (
                prediction.market_alternatives
                or []
            ),
        }
        for prediction in predictions
    ]
    league_map_rows = session.execute(
        text(
            """
            SELECT
                p.id AS prediction_id,
                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                m.kickoff_datetime,
                m.status,
                m.is_finished,
                m.is_postponed,
                m.is_cancelled
            FROM predictions p
            JOIN matches m
                ON m.id = p.match_id
            WHERE p.slate = :slate
            """
        ),
        {"slate": slate},
    ).mappings().all()

    match_info_by_prediction_id = {
        int(row["prediction_id"]): dict(row)
        for row in league_map_rows
    }

    filtered_candidates = []

    blocked_statuses = {
        "FT",
        "AET",
        "PEN",
        "LIVE",
        "1H",
        "2H",
        "HT",
        "BREAK",
        "INT",
        "PST",
        "CANC",
        "ABD",
    }

    for item in candidate_dicts:

        info = match_info_by_prediction_id.get(
            int(item["prediction_id"]),
            {},
        )

        item["league"] = info.get("league")
        item["home_team"] = info.get(
            "home_team"
        )
        item["away_team"] = info.get(
            "away_team"
        )
        item["kickoff_date"] = info.get(
            "kickoff_date"
        )
        item["kickoff_datetime"] = info.get(
            "kickoff_datetime"
        )

        item["kickoff_time"] = (
            _candidate_kickoff_time(item)
        )

        if info.get("is_finished"):
            continue

        if info.get("is_postponed"):
            continue

        if info.get("is_cancelled"):
            continue

        status = str(
            info.get("status") or ""
        ).upper()

        if status in blocked_statuses:
            continue

        timing = analyze_prediction_timing(
            kickoff_value=(
                item.get(
                    "kickoff_datetime"
                )
                or item.get("kickoff_date")
            )
        )

        if (
            timing.minutes_to_kickoff
            is not None
            and timing.minutes_to_kickoff <= 8
        ):
            continue

        survivability = (
            evaluate_odds_survivability(
                market=item["market"],
                bookmaker=item.get(
                    "odds_bookmaker"
                ),
                odds_retrieved_at=item.get(
                    "odds_retrieved_at"
                ),
                minutes_to_kickoff=(
                    timing.minutes_to_kickoff
                ),
            )
        )

        if not survivability.allowed:
            continue

        item["survivability_score"] = (
            survivability.survivability_score
        )

        item["stale_odds"] = (
            survivability.stale
        )

        item["execution_ready"] = (
            survivability.survivability_score
            >= 0.50
            and not survivability.stale
        )

        if not item["execution_ready"]:
            continue

        filtered_candidates.append(item)

    approved_dicts, league_rejections = (
        filter_candidate_dicts_by_league_quality(
            session=session,
            candidates=filtered_candidates,
            mode=league_odds_filter_mode,
        )
    )

    _diag(
        "fallback_league_approved",
        len(approved_dicts),
    )

    _diag(
        "fallback_league_rejected",
        len(league_rejections),
    )

    predictions = [
        item["prediction"]
        for item in approved_dicts
    ]

    best_prediction_by_match: dict[
        int,
        Prediction,
    ] = {}

    for prediction in predictions:

        current_best = (
            best_prediction_by_match.get(
                prediction.match_id
            )
        )

        if (
            current_best is None
            or _fallback_ranking_score(
                prediction
            )
            > _fallback_ranking_score(
                current_best
            )
        ):
            best_prediction_by_match[
                prediction.match_id
            ] = prediction

    ranked_games = sorted(
        best_prediction_by_match.values(),
        key=lambda prediction: (
            -_fallback_ranking_score(
                prediction
            ),
            prediction.id,
        ),
    )

    if len(ranked_games) < MIN_GAMES_PER_GROUP:
        return {
            "message": {
                "status": (
                    "not_enough_predictions"
                ),
                "available_games": float(
                    len(ranked_games)
                ),
                "reason": (
                    "Not enough strict "
                    "best-pick predictions "
                    "passed filters."
                ),
            }
        }

    session.execute(
        delete(PredictionGroupItem).where(
            PredictionGroupItem.slate
            == slate,
        )
    )

    group_summaries: dict[str, Any] = {}

    remaining_games = ranked_games.copy()

    daily_exposure_used = 0.0

    for group_number in range(
        1,
        MAX_GROUPS + 1,
    ):

        group_name = (
            f"Group {group_number}"
        )

        selected_games = (
            _select_safe_fallback_group(
                available_games=remaining_games,
                min_group_odds=min_group_odds,
                max_group_odds=max_group_odds,
                min_group_size=MIN_GAMES_PER_GROUP,
                max_group_size=MAX_GAMES_PER_GROUP,
            )
        )

        if (
            len(selected_games)
            < MIN_GAMES_PER_GROUP
        ):
            break

        selected_match_ids = {
            game.match_id
            for game in selected_games
        }

        remaining_games = [
            candidate
            for candidate in remaining_games
            if candidate.match_id
            not in selected_match_ids
        ]

        cumulative_odds = (
            _cumulative_odds(
                selected_games
            )
        )

        if cumulative_odds is None:
            continue

        if (
            cumulative_odds
            < min_group_odds
            or cumulative_odds
            > max_group_odds
        ):
            continue

        odds_values = [
            float(prediction.odds or 0.0)
            for prediction in selected_games
            if prediction.odds is not None
        ]

        confidence_values = [
            float(
                prediction.confidence or 0.0
            )
            for prediction in selected_games
        ]

        group_tier = "SAFE"

        stake_decision = (
            calculate_group_stake(
                bankroll=bankroll,
                odds_values=odds_values,
                confidence_values=(
                    confidence_values
                ),
                tier=group_tier,
                flat_stake=flat_stake,
                daily_exposure_used=(
                    daily_exposure_used
                ),
            )
        )

        daily_exposure_used += (
            stake_decision.stake
        )

        for prediction in selected_games:

            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=prediction.id,
                )
            )

        group_matches = (
            _build_fallback_group_matches(
                session=session,
                selected_games=selected_games,
            )
        )

        group_summaries[group_name] = {
            "group_type": (
                "STRICT_FALLBACK_BEST_PICKS"
            ),
            "average_confidence": round(
                mean(
                    [
                        p.confidence
                        for p in selected_games
                    ]
                ),
                4,
            ),
            "average_value_score": round(
                mean(
                    [
                        (
                            p.value_score
                            or 0.0
                        )
                        for p in selected_games
                    ]
                ),
                4,
            ),
            "cumulative_odds": round(
                cumulative_odds,
                4,
            ),
            "games": float(
                len(selected_games)
            ),
            "odds_coverage": 1.0,
            "group_tier": (
                "FALLBACK_SAFE"
            ),
            "recommended_stake": (
                stake_decision.stake
            ),
            "stake_method": (
                stake_decision.method
            ),
            "stake_reason": (
                stake_decision.reason
            ),
            "bankroll_pct": (
                stake_decision.bankroll_pct
            ),
            "raw_kelly_fraction": (
                stake_decision.raw_kelly_fraction
            ),
            "applied_fraction": (
                stake_decision.applied_fraction
            ),
            "estimated_group_probability": (
                stake_decision.estimated_probability
            ),
            "group_matches": (
                group_matches
            ),
            "expected_value": (
                stake_decision.expected_value
            ),
        }

    session.commit()

    if not group_summaries:
        return {
            "message": {
                "status": (
                    "no_safe_fallback_groups"
                ),
                "reason": (
                    "Predictions existed, "
                    "but no strict fallback "
                    "groups fit production limits."
                ),
            }
        }

    return group_summaries

def _build_fallback_group_matches(
    session: Session,
    selected_games: list[Prediction],
) -> list[dict[str, Any]]:

    prediction_ids = [
        int(prediction.id)
        for prediction in selected_games
    ]

    if not prediction_ids:
        return []

    rows = session.execute(
        text(
            """
            SELECT
                p.id AS prediction_id,
                p.match_id,
                p.market,
                p.predicted_label,
                p.odds,
                p.confidence,
                p.value_score,

                p.odds_bookmaker,
                p.odds_market,
                p.odds_selection,
                p.odds_match_quality,
                p.odds_retrieved_at,

                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                m.kickoff_datetime

            FROM predictions p

            JOIN matches m
                ON m.id = p.match_id

            WHERE p.id = ANY(:prediction_ids)
            """
        ),
        {
            "prediction_ids": prediction_ids,
        },
    ).mappings().all()

    items = []

    for row in rows:

        item = dict(row)

        item["kickoff_time"] = (
            _candidate_kickoff_time(item)
        )

        item["executable_label"] = (
            _render_executable_label(item)
        )

        timing = analyze_prediction_timing(
            kickoff_value=(
                item.get(
                    "kickoff_datetime"
                )
                or item.get(
                    "kickoff_date"
                )
            )
        )

        survivability = (
            evaluate_odds_survivability(
                market=item["market"],
                bookmaker=item.get(
                    "odds_bookmaker"
                ),
                odds_retrieved_at=item.get(
                    "odds_retrieved_at"
                ),
                minutes_to_kickoff=(
                    timing.minutes_to_kickoff
                ),
            )
        )

        survivability_bucket = (
            "ELITE"
            if survivability.survivability_score
            >= 0.80
            else (
                "STRONG"
                if survivability.survivability_score
                >= 0.65
                else (
                    "MODERATE"
                    if survivability.survivability_score
                    >= 0.50
                    else "WEAK"
                )
            )
        )

        execution_ready = (
            survivability_bucket
            in {"ELITE", "STRONG"}
            and not survivability.stale
        )

        items.append(
            {
                "prediction_id": item.get(
                    "prediction_id"
                ),
                "match_id": item.get(
                    "match_id"
                ),
                "league": item.get(
                    "league"
                ),
                "home_team": item.get(
                    "home_team"
                ),
                "away_team": item.get(
                    "away_team"
                ),

                "kickoff_time": item.get(
                    "kickoff_time"
                ),

                "minutes_to_kickoff": (
                    timing.minutes_to_kickoff
                ),

                "timing_status": (
                    timing.timing_status
                ),

                "recommended_action": (
                    timing.recommended_action
                ),

                "timing_reason": (
                    timing.reason
                ),

                "market": item.get(
                    "market"
                ),

                "predicted_label": item.get(
                    "predicted_label"
                ),

                "executable_label": item.get(
                    "executable_label"
                ),

                "odds": item.get(
                    "odds"
                ),

                "confidence": item.get(
                    "confidence"
                ),

                "value_score": item.get(
                    "value_score"
                ),

                "bookmaker": item.get(
                    "odds_bookmaker"
                ),

                "odds_market": item.get(
                    "odds_market"
                ),

                "odds_selection": item.get(
                    "odds_selection"
                ),

                "odds_match_quality": item.get(
                    "odds_match_quality"
                ),

                "survivability_score": (
                    survivability.survivability_score
                ),

                "freshness_score": (
                    survivability.freshness_score
                ),

                "persistence_score": (
                    survivability.persistence_score
                ),

                "downgrade_risk_score": (
                    survivability.downgrade_risk_score
                ),

                "fallback_markets": (
                    survivability.fallback_markets
                ),

                "primary_fallback_market": (
                    survivability.fallback_markets[0]
                    if survivability.fallback_markets
                    else None
                ),

                "stale_odds": (
                    survivability.stale
                ),

                "survivability_bucket": (
                    survivability_bucket
                ),

                "execution_ready": (
                    execution_ready
                ),

                "survivability_reasons": (
                    survivability.reasons
                ),
            }
        )

    return sorted(
        items,
        key=lambda item: (
            str(
                item.get(
                    "kickoff_time"
                ) or ""
            ),
            -float(
                item.get(
                    "survivability_score"
                ) or 0.0
            ),
            int(
                item.get(
                    "prediction_id"
                ) or 0
            ),
        ),
    )

def _select_safe_fallback_group(
    available_games: list[Prediction],
    min_group_odds: float,
    max_group_odds: float,
    min_group_size: int,
    max_group_size: int,
) -> list[Prediction]:

    selected: list[Prediction] = []

    used_match_ids: set[int] = set()

    used_markets: set[str] = set()

    used_families: set[str] = set()

    for candidate in available_games:

        if candidate.match_id in used_match_ids:
            continue

        if candidate.market in used_markets:
            continue

        executable = parse_executable_market(
            candidate.market
        )

        family = executable.family

        if family in used_families:
            continue

        if candidate.odds is None:
            continue

        odds = float(candidate.odds)

        if odds < 1.30 or odds > 4.20:
            continue

        if (
            candidate.value_score is None
            or candidate.value_score
            < STRICT_GROUPING_MIN_VALUE_SCORE
        ):
            continue

        if (
            candidate.confidence
            < STRICT_GROUPING_MIN_CONFIDENCE
        ):
            continue

        timing = analyze_prediction_timing(
            kickoff_value=(
                getattr(
                    candidate,
                    "kickoff_datetime",
                    None,
                )
                or getattr(
                    candidate,
                    "kickoff_date",
                    None,
                )
            )
        )

        if (
            timing.minutes_to_kickoff
            is not None
            and timing.minutes_to_kickoff <= 8
        ):
            continue

        survivability = (
            evaluate_odds_survivability(
                market=candidate.market,
                bookmaker=getattr(
                    candidate,
                    "odds_bookmaker",
                    None,
                ),
                odds_retrieved_at=getattr(
                    candidate,
                    "odds_retrieved_at",
                    None,
                ),
                minutes_to_kickoff=(
                    timing.minutes_to_kickoff
                ),
            )
        )

        if not survivability.allowed:
            continue

        if survivability.stale:
            continue

        if (
            survivability.survivability_score
            < 0.50
        ):
            continue

        if (
            executable.family
            == "ASIAN_HANDICAP"
            and timing.minutes_to_kickoff
            is not None
            and timing.minutes_to_kickoff <= 35
        ):
            continue

        if (
            executable.volatility_tier
            == "EXTREME"
        ):
            continue

        test_group = selected + [candidate]

        test_odds = _cumulative_odds(
            test_group
        )

        if test_odds is None:
            continue

        if test_odds > max_group_odds:
            continue

        selected.append(candidate)

        used_match_ids.add(
            candidate.match_id
        )

        used_markets.add(
            candidate.market
        )

        used_families.add(family)

        if (
            len(selected)
            >= min_group_size
            and test_odds >= min_group_odds
        ):
            return selected

        if len(selected) >= max_group_size:
            break

    final_odds = _cumulative_odds(
        selected
    )

    if (
        len(selected) >= min_group_size
        and final_odds is not None
        and (
            min_group_odds
            <= final_odds
            <= max_group_odds
        )
    ):
        return selected

    return []

def _fallback_ranking_score(
    prediction: Prediction,
) -> float:

    value_score = float(
        prediction.value_score or 0.0
    )

    confidence = float(
        prediction.confidence or 0.0
    )

    odds = float(
        prediction.odds or 0.0
    )

    odds_component = 0.0

    if 1.30 <= odds <= 1.80:
        odds_component = 0.10

    elif 1.80 < odds <= 2.50:
        odds_component = 0.12

    elif 2.50 < odds <= 3.20:
        odds_component = 0.04

    elif odds > 3.20:
        odds_component = -0.10

    elif 0 < odds < 1.30:
        odds_component = -0.30

    executable = parse_executable_market(
        prediction.market
    )

    survivability_bonus = 0.0

    timing_penalty = 0.0

    if (
        executable.family
        == "ASIAN_HANDICAP"
    ):
        survivability_bonus -= 0.05

    if (
        executable.volatility_tier
        == "HIGH"
    ):
        survivability_bonus -= 0.04

    elif (
        executable.volatility_tier
        == "EXTREME"
    ):
        survivability_bonus -= 0.12

    if getattr(
        prediction,
        "odds_match_quality",
        None,
    ) == "exact_executable_market":
        survivability_bonus += 0.08

    if getattr(
        prediction,
        "odds_bookmaker",
        None,
    ):
        survivability_bonus += 0.04

    timing = analyze_prediction_timing(
        kickoff_value=(
            getattr(
                prediction,
                "kickoff_datetime",
                None,
            )
            or getattr(
                prediction,
                "kickoff_date",
                None,
            )
        )
    )

    if (
        timing.minutes_to_kickoff
        is not None
    ):

        if timing.minutes_to_kickoff <= 15:
            timing_penalty -= 0.20

        elif timing.minutes_to_kickoff <= 35:
            timing_penalty -= 0.10

        elif timing.minutes_to_kickoff <= 60:
            timing_penalty -= 0.04

    return (
        confidence * 0.46
        + value_score * 0.40
        + odds_component
        + survivability_bonus
        + timing_penalty
    )


def _cumulative_odds(
    predictions: list[Prediction],
) -> float | None:

    odds_values = [
        p.odds
        for p in predictions
        if p.odds is not None
    ]

    if len(odds_values) != len(predictions):
        return None

    total = float(prod(odds_values))

    if total <= 1.0:
        return None

    return round(total, 4)