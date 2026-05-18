# backend/app/grouping/create_groups.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import prod
from statistics import mean
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

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

    min_odds: float = 1.30
    max_odds: float = 4.20

    min_group_odds: float = PRODUCTION_MIN_GROUP_ODDS
    max_group_odds: float = PRODUCTION_MAX_GROUP_ODDS

    min_market_roi: float = -0.05
    min_league_roi: float = -0.08
    min_band_roi: float = -0.08

    max_same_family_per_group: int = 1
    min_sample_size: int = 10

    max_same_market_per_group: int = 1
    max_same_league_per_group: int = 1

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
                "reason": "No approved profile produced a strict profitable group.",
            }
        }

    if profile:
        profile_config = PROFILE_CONFIGS.get(profile)

        if profile_config is None:
            raise ValueError(f"Unknown profile: {profile}")

        min_confidence = float(profile_config["min_confidence"])

    config = PortfolioGroupConfig(
        min_confidence=max(float(min_confidence), STRICT_GROUPING_MIN_CONFIDENCE),
        min_group_odds=max(float(min_group_odds), PRODUCTION_MIN_GROUP_ODDS),
        max_group_odds=PRODUCTION_MAX_GROUP_ODDS,
        min_sample_size=10,
        use_intelligence_filters=use_intelligence_filters,
        league_odds_filter_mode=league_odds_filter_mode,
        bankroll=float(bankroll),
        max_odds=(
            min(float(profile_config["max_odds"]), 4.20)
            if profile_config
            else 4.20
        ),
    )

    portfolio_groups = _build_profitability_aware_groups(
        session=session,
        slate=slate,
        config=config,
        require_odds=require_odds,
    )

    if portfolio_groups:
        _save_groups(
            session=session,
            slate=slate,
            groups=portfolio_groups,
        )
        session.commit()
        return _summarize_portfolio_groups(
            groups=portfolio_groups,
            config=config,
        )

    if profile:
        return {
            "message": {
                "status": "no_profile_qualified_groups",
                "profile": profile,
                "reason": "No picks passed strict profitability filters.",
            }
        }

    return _fallback_confidence_groups(
        session=session,
        slate=slate,
        min_confidence=config.min_confidence,
        min_group_odds=config.min_group_odds,
        max_group_odds=config.max_group_odds,
        require_odds=require_odds,
        league_odds_filter_mode=league_odds_filter_mode,
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
        _diag("market_intel", "missing_market_intelligence")
        return []

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
            continue

        match_id = int(enriched["match_id"])
        current_best = best_by_match.get(match_id)

        if current_best is None or _best_grouping_pick_score(enriched) > _best_grouping_pick_score(current_best):
            best_by_match[match_id] = enriched

    _diag("best_by_match", len(best_by_match))

    enriched_candidates = sorted(
        best_by_match.values(),
        key=lambda item: (
            item.get("portfolio_tier") != "SAFE",
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

    _diag("recommendation_approved_source", len(approved_source))

    approved_candidates: list[dict[str, Any]] = []
    rejection_counts: dict[str, int] = {}

    for pick in approved_source:
        reason = None

        market = str(pick.get("market") or "")
        missing_market_intel = market not in market_intel

        if pick.get("risk_level") == "AVOID":
            reason = "risk_level_avoid"

        elif pick.get("portfolio_tier") not in {"SAFE", "MODERATE"}:
            reason = "portfolio_tier"

        elif float(pick.get("portfolio_risk_score") or 999.0) > STRICT_MAX_PORTFOLIO_RISK:
            reason = "risk_score"

        elif float(pick.get("confidence") or 0.0) < config.min_confidence:
            reason = "confidence"

        elif float(pick.get("value_score") or 0.0) < config.min_value_score:
            reason = "value_score"

        elif pick.get("odds_match_quality") != "exact_executable_market":
            reason = "odds_quality"

        elif (
            not missing_market_intel
            and float(pick.get("production_score") or 0.0) < STRICT_MIN_PRODUCTION_SCORE
        ):
            reason = "production_score"

        elif (
            missing_market_intel
            and float(pick.get("confidence") or 0.0) < 0.64
        ):
            reason = "missing_market_intel_confidence"

        elif (
            missing_market_intel
            and float(pick.get("value_score") or 0.0) < 0.06
        ):
            reason = "missing_market_intel_value"

        if reason:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            continue

        approved_candidates.append(pick)

    approved_candidates = approved_candidates[:MAX_APPROVED_CANDIDATES]

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

    odds_filter = "AND p.odds IS NOT NULL" if require_odds else ""

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
            m.league,
            m.home_team,
            m.away_team,
            m.kickoff_date,
            m.kickoff_datetime
        FROM predictions p
        JOIN matches m ON m.id = p.match_id
        WHERE p.slate = :slate
          AND p.confidence >= :min_confidence
          AND p.market = ANY(:enabled_markets)
          AND p.value_score IS NOT NULL
          AND p.value_score >= :min_value_score
          AND p.odds_match_quality = 'exact_executable_market'
          AND p.odds_bookmaker IS NOT NULL
          {odds_filter}
        ORDER BY
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

    candidates = [dict(row._mapping) for row in rows]

    for candidate in candidates:
        candidate["kickoff_time"] = _candidate_kickoff_time(candidate)

    return candidates


def _prefer_best_odds_candidates(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    best: dict[tuple[int, str, str], dict[str, Any]] = {}

    for prediction in predictions:
        key = (
            int(prediction["match_id"]),
            str(prediction["market"]),
            str(prediction["predicted_label"]),
        )

        current = best.get(key)

        if current is None or _best_odds_quality_score(prediction) > _best_odds_quality_score(current):
            best[key] = prediction

    return sorted(
        best.values(),
        key=lambda item: (
            -_best_odds_quality_score(item),
            -float(item.get("value_score") or 0.0),
            -float(item.get("confidence") or 0.0),
            float(item.get("odds") or 999.0),
            int(item["prediction_id"]),
        ),
    )


def _best_odds_quality_score(prediction: dict[str, Any]) -> float:
    quality = prediction.get("odds_match_quality") or "none"
    odds = prediction.get("odds")
    value_score = float(prediction.get("value_score") or 0.0)
    confidence = float(prediction.get("confidence") or 0.0)

    quality_points = {
        "exact_executable_market": 130.0,
        "exact_canonical": 90.0,
        "exact_market_fallback": 75.0,
        "direct": 50.0,
    }.get(str(quality), 10.0)

    odds_points = 0.0

    if odds is not None:
        selected_odds = float(odds)

        if 1.35 <= selected_odds <= 2.20:
            odds_points += 16.0
        elif 2.20 < selected_odds <= 3.00:
            odds_points += 8.0
        elif selected_odds > 4.20:
            odds_points -= 35.0
        elif selected_odds < 1.30:
            odds_points -= 40.0

    bookmaker_points = 10.0 if prediction.get("odds_bookmaker") else -25.0

    return round(
        quality_points
        + bookmaker_points
        + min(value_score * 120.0, 28.0)
        + min(confidence * 12.0, 12.0)
        + odds_points,
        4,
    )


def _best_grouping_pick_score(prediction: dict[str, Any]) -> float:
    return round(
        float(prediction.get("selection_score") or 0.0)
        + (_best_odds_quality_score(prediction) / 800.0)
        - (float(prediction.get("portfolio_risk_score") or 0.0) / 600.0),
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

    executable = parse_executable_market(market)

    if executable.execution_risk == "HIGH" or executable.volatility_tier == "EXTREME":
        return None

    if market not in enabled_markets:
        return None

    confidence = float(prediction["confidence"] or 0.0)
    value_score = float(prediction["value_score"] or 0.0)
    odds = prediction.get("odds")

    if odds is None:
        return None

    odds = float(odds)

    if confidence < config.min_confidence:
        return None

    if value_score < config.min_value_score:
        return None

    if odds < config.min_odds or odds > config.max_odds:
        return None

    if prediction.get("odds_match_quality") != "exact_executable_market":
        return None

    if not prediction.get("odds_bookmaker"):
        return None

    missing_market_intel = market not in market_intel

    if missing_market_intel:
        if confidence < 0.64:
            return None

        if value_score < 0.06:
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
            strict=True,
        )

        if not filter_result.allowed:
            return None

        prediction["portfolio_allowed"] = filter_result.allowed
        prediction["portfolio_filter_reason"] = filter_result.reason
        prediction["portfolio_risk_flags"] = filter_result.risk_flags
        prediction["portfolio_risk_score"] = filter_result.risk_score
        prediction["portfolio_tier"] = filter_result.tier
    else:
        prediction["portfolio_allowed"] = True
        prediction["portfolio_filter_reason"] = "Not used"
        prediction["portfolio_risk_flags"] = []
        prediction["portfolio_risk_score"] = 0.0
        prediction["portfolio_tier"] = "UNFILTERED"

    if prediction["portfolio_tier"] not in {"SAFE", "MODERATE"}:
        return None

    if float(prediction["portfolio_risk_score"]) > STRICT_MAX_PORTFOLIO_RISK:
        return None

    market_data = market_intel.get(
        market,
        {
            "roi": 0.0,
            "hit_rate": 0.0,
            "sample_size": 0,
        },
    )

    league_data = league_market_intel.get((league, market))
    odds_data = odds_band_intel.get((market, odds_band(odds)))
    confidence_data = confidence_band_intel.get((market, confidence_band(confidence)))

    market_roi = float(market_data.get("roi") or 0.0)
    market_hit_rate = float(market_data.get("hit_rate") or 0.0)
    market_sample_size = int(market_data.get("sample_size") or 0)

    league_roi = float(league_data.get("roi") or 0.0) if league_data else 0.0
    league_hit_rate = float(league_data.get("hit_rate") or 0.0) if league_data else 0.0
    league_sample_size = int(league_data.get("sample_size") or 0) if league_data else 0

    odds_band_roi = float(odds_data.get("roi") or 0.0) if odds_data else 0.0
    odds_band_hit_rate = float(odds_data.get("hit_rate") or 0.0) if odds_data else 0.0
    odds_band_sample_size = int(odds_data.get("sample_size") or 0) if odds_data else 0

    confidence_band_roi = float(confidence_data.get("roi") or 0.0) if confidence_data else 0.0
    confidence_band_hit_rate = float(confidence_data.get("hit_rate") or 0.0) if confidence_data else 0.0
    confidence_band_sample_size = int(confidence_data.get("sample_size") or 0) if confidence_data else 0

    if not missing_market_intel and market_roi < config.min_market_roi:
        return None

    if league_sample_size >= config.min_sample_size and league_roi < config.min_league_roi:
        return None

    if odds_band_sample_size >= config.min_sample_size and odds_band_roi < config.min_band_roi:
        return None

    if confidence_band_sample_size >= config.min_sample_size and confidence_band_roi < config.min_band_roi:
        return None

    sample_penalty = _sample_penalty(
        market_sample_size=market_sample_size,
        league_sample_size=league_sample_size,
        odds_band_sample_size=odds_band_sample_size,
        confidence_band_sample_size=confidence_band_sample_size,
        min_sample_size=config.min_sample_size,
        missing_market_intel=missing_market_intel,
    )

    odds_quality = _odds_quality_component(odds)
    risk_penalty = max(float(prediction.get("portfolio_risk_score") or 0.0), 0.0) / 110.0
    odds_match_quality_score = _best_odds_quality_score(prediction)
    bookmaker_execution_score = odds_match_quality_score / 100.0

    selection_score = (
        confidence * 0.30
        + value_score * 0.32
        + market_roi * 0.12
        + league_roi * 0.10
        + odds_band_roi * 0.06
        + confidence_band_roi * 0.06
        + odds_quality * 0.08
        + bookmaker_execution_score * 0.10
        - sample_penalty
        - risk_penalty
    )

    prediction["kickoff_time"] = _candidate_kickoff_time(prediction)
    prediction["market_family"] = executable.family
    prediction["missing_market_intel"] = missing_market_intel
    prediction["market_roi"] = market_roi
    prediction["market_hit_rate"] = market_hit_rate
    prediction["market_sample_size"] = market_sample_size
    prediction["league_roi"] = league_roi
    prediction["league_hit_rate"] = league_hit_rate
    prediction["league_sample_size"] = league_sample_size
    prediction["odds_band"] = odds_band(odds)
    prediction["odds_band_roi"] = odds_band_roi
    prediction["odds_band_hit_rate"] = odds_band_hit_rate
    prediction["odds_band_sample_size"] = odds_band_sample_size
    prediction["confidence_band"] = confidence_band(confidence)
    prediction["confidence_band_roi"] = confidence_band_roi
    prediction["confidence_band_hit_rate"] = confidence_band_hit_rate
    prediction["confidence_band_sample_size"] = confidence_band_sample_size
    prediction["bookmaker_execution_score"] = bookmaker_execution_score
    prediction["odds_match_quality_score"] = odds_match_quality_score
    prediction["selection_score"] = selection_score

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
        penalty += 0.035
    elif market_sample_size < min_sample_size * 2:
        penalty += 0.03

    if league_sample_size == 0:
        penalty += 0.04
    elif league_sample_size < min_sample_size:
        penalty += 0.03

    if odds_band_sample_size == 0:
        penalty += 0.03

    if confidence_band_sample_size == 0:
        penalty += 0.03

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
            float(item.get("portfolio_risk_score") or 999.0),
            -float(item.get("selection_score") or 0.0),
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

            if not _candidate_fits_group(candidate, group, config):
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

        if len(group) >= config.min_group_size and _group_odds_within_limits(
            group=group,
            min_group_odds=config.min_group_odds,
            max_group_odds=config.max_group_odds,
        ):
            groups.append(group)
        else:
            for item in group:
                used_match_ids.discard(int(item["match_id"]))
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

    cumulative = float(prod(odds_values))
    return min_group_odds <= cumulative <= max_group_odds


def _candidate_fits_group(
    candidate: dict[str, Any],
    group: list[dict[str, Any]],
    config: PortfolioGroupConfig,
) -> bool:
    market = candidate["market"]
    league = candidate.get("league") or "unknown"
    market_family = candidate.get("market_family") or _resolve_group_market_family(market)

    same_market_count = sum(1 for item in group if item["market"] == market)
    same_league_count = sum(1 for item in group if (item.get("league") or "unknown") == league)
    same_family_count = sum(
        1
        for item in group
        if (item.get("market_family") or _resolve_group_market_family(item["market"])) == market_family
    )

    if same_market_count >= config.max_same_market_per_group:
        return False

    if same_league_count >= config.max_same_league_per_group:
        return False

    if same_family_count >= config.max_same_family_per_group:
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


def _resolve_group_market_family(market: str) -> str:
    return parse_executable_market(market).family


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

    for group_index, group in enumerate(groups, start=1):
        group_name = f"Portfolio Group {group_index}"

        for item in group:
            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=int(item["prediction_id"]),
                )
            )


def _summarize_portfolio_groups(
    groups: list[list[dict[str, Any]]],
    config: PortfolioGroupConfig,
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    daily_exposure_used = 0.0

    for group_index, group in enumerate(groups, start=1):
        group_name = f"Portfolio Group {group_index}"

        odds_values = [float(item["odds"]) for item in group if item.get("odds") is not None]
        confidence_values = [float(item["confidence"] or 0.0) for item in group]
        risk_scores = [float(item.get("portfolio_risk_score") or 0.0) for item in group]

        average_risk_score = mean(risk_scores) if risk_scores else 0.0
        max_risk_score = max(risk_scores) if risk_scores else 0.0

        group_tier = resolve_group_tier(
            average_risk_score=average_risk_score,
            max_risk_score=max_risk_score,
            rejected_picks=0,
        )

        cumulative_odds = float(prod(odds_values)) if len(odds_values) == len(group) else 0.0

        if cumulative_odds > config.max_group_odds:
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

        group_matches = [
            {
                "match_id": item.get("match_id"),
                "league": item.get("league"),
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
                "kickoff_time": _candidate_kickoff_time(item),
                "market": item.get("market"),
                "predicted_label": item.get("predicted_label"),
                "odds": item.get("odds"),
                "confidence": item.get("confidence"),
                "value_score": item.get("value_score"),
                "bookmaker": item.get("odds_bookmaker"),
                "odds_match_quality": item.get("odds_match_quality"),
                "missing_market_intel": item.get("missing_market_intel"),
            }
            for item in group
        ]

        summaries[group_name] = {
            "group_type": "STRICT_BEST_PICKS_PORTFOLIO",
            "group_tier": group_tier,
            "games": float(len(group)),
            "average_confidence": round(mean(confidence_values), 4),
            "average_value_score": round(mean(float(item["value_score"] or 0.0) for item in group), 4),
            "average_market_roi": round(mean(float(item["market_roi"] or 0.0) for item in group), 4),
            "average_league_roi": round(mean(float(item["league_roi"] or 0.0) for item in group), 4),
            "average_odds_band_roi": round(mean(float(item["odds_band_roi"] or 0.0) for item in group), 4),
            "average_confidence_band_roi": round(mean(float(item["confidence_band_roi"] or 0.0) for item in group), 4),
            "average_selection_score": round(mean(float(item["selection_score"] or 0.0) for item in group), 4),
            "average_odds_quality_score": round(mean(float(item.get("odds_match_quality_score") or 0.0) for item in group), 4),
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
            "group_matches": group_matches,
            "expected_value": stake_decision.expected_value,
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
    enabled_markets = set(get_enabled_markets(session))

    query = (
        select(Prediction)
        .where(
            Prediction.slate == slate,
            Prediction.confidence >= max(min_confidence, STRICT_GROUPING_MIN_CONFIDENCE),
            Prediction.market.in_(enabled_markets),
            Prediction.value_score.isnot(None),
            Prediction.value_score >= STRICT_GROUPING_MIN_VALUE_SCORE,
            Prediction.odds_match_quality == "exact_executable_market",
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

    predictions = list(session.scalars(query))

    candidate_dicts = [
        {
            "prediction_id": prediction.id,
            "match_id": prediction.match_id,
            "league": None,
            "home_team": None,
            "away_team": None,
            "kickoff_time": None,
            "market": prediction.market,
            "predicted_label": prediction.predicted_label,
            "sport": prediction.sport,
            "prediction": prediction,
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
                m.kickoff_datetime
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.slate = :slate
            """
        ),
        {"slate": slate},
    ).mappings().all()

    match_info_by_prediction_id = {
        int(row["prediction_id"]): dict(row)
        for row in league_map_rows
    }

    for item in candidate_dicts:
        info = match_info_by_prediction_id.get(int(item["prediction_id"]), {})
        item["league"] = info.get("league")
        item["home_team"] = info.get("home_team")
        item["away_team"] = info.get("away_team")
        item["kickoff_date"] = info.get("kickoff_date")
        item["kickoff_datetime"] = info.get("kickoff_datetime")
        item["kickoff_time"] = _candidate_kickoff_time(item)

    approved_dicts, league_rejections = filter_candidate_dicts_by_league_quality(
        session=session,
        candidates=candidate_dicts,
        mode=league_odds_filter_mode,
    )

    _diag("fallback_league_approved", len(approved_dicts))
    _diag("fallback_league_rejected", len(league_rejections))

    predictions = [item["prediction"] for item in approved_dicts]

    best_prediction_by_match: dict[int, Prediction] = {}

    for prediction in predictions:
        current_best = best_prediction_by_match.get(prediction.match_id)

        if current_best is None or _fallback_ranking_score(prediction) > _fallback_ranking_score(current_best):
            best_prediction_by_match[prediction.match_id] = prediction

    ranked_games = sorted(
        best_prediction_by_match.values(),
        key=lambda prediction: (
            -_fallback_ranking_score(prediction),
            prediction.id,
        ),
    )

    if len(ranked_games) < MIN_GAMES_PER_GROUP:
        return {
            "message": {
                "status": "not_enough_predictions",
                "available_games": float(len(ranked_games)),
                "reason": "Not enough strict best-pick predictions passed filters.",
            }
        }

    session.execute(
        delete(PredictionGroupItem).where(
            PredictionGroupItem.slate == slate,
        )
    )

    group_summaries: dict[str, Any] = {}
    remaining_games = ranked_games.copy()
    daily_exposure_used = 0.0

    for group_number in range(1, MAX_GROUPS + 1):
        group_name = f"Group {group_number}"

        selected_games = _select_safe_fallback_group(
            available_games=remaining_games,
            min_group_odds=min_group_odds,
            max_group_odds=max_group_odds,
            min_group_size=MIN_GAMES_PER_GROUP,
            max_group_size=MAX_GAMES_PER_GROUP,
        )

        if len(selected_games) < MIN_GAMES_PER_GROUP:
            break

        selected_match_ids = {game.match_id for game in selected_games}

        remaining_games = [
            candidate
            for candidate in remaining_games
            if candidate.match_id not in selected_match_ids
        ]

        cumulative_odds = _cumulative_odds(selected_games)

        if cumulative_odds is None:
            continue

        if cumulative_odds < min_group_odds or cumulative_odds > max_group_odds:
            continue

        odds_values = [float(prediction.odds or 0.0) for prediction in selected_games if prediction.odds is not None]
        confidence_values = [float(prediction.confidence or 0.0) for prediction in selected_games]

        group_tier = "SAFE"

        stake_decision = calculate_group_stake(
            bankroll=bankroll,
            odds_values=odds_values,
            confidence_values=confidence_values,
            tier=group_tier,
            flat_stake=flat_stake,
            daily_exposure_used=daily_exposure_used,
        )

        daily_exposure_used += stake_decision.stake

        for prediction in selected_games:
            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=prediction.id,
                )
            )

        group_matches = _build_fallback_group_matches(
            session=session,
            selected_games=selected_games,
        )

        group_summaries[group_name] = {
            "group_type": "STRICT_FALLBACK_BEST_PICKS",
            "average_confidence": round(mean([p.confidence for p in selected_games]), 4),
            "average_value_score": round(mean([(p.value_score or 0.0) for p in selected_games]), 4),
            "cumulative_odds": round(cumulative_odds, 4),
            "games": float(len(selected_games)),
            "odds_coverage": 1.0,
            "group_tier": "FALLBACK_SAFE",
            "recommended_stake": stake_decision.stake,
            "stake_method": stake_decision.method,
            "stake_reason": stake_decision.reason,
            "bankroll_pct": stake_decision.bankroll_pct,
            "raw_kelly_fraction": stake_decision.raw_kelly_fraction,
            "applied_fraction": stake_decision.applied_fraction,
            "estimated_group_probability": stake_decision.estimated_probability,
            "group_matches": group_matches,
            "expected_value": stake_decision.expected_value,
        }

    session.commit()

    if not group_summaries:
        return {
            "message": {
                "status": "no_safe_fallback_groups",
                "reason": "Predictions existed, but no strict fallback groups fit production limits.",
            }
        }

    return group_summaries


def _build_fallback_group_matches(
    session: Session,
    selected_games: list[Prediction],
) -> list[dict[str, Any]]:
    prediction_ids = [int(prediction.id) for prediction in selected_games]

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
                p.odds_match_quality,
                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                m.kickoff_datetime
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.id = ANY(:prediction_ids)
            """
        ),
        {"prediction_ids": prediction_ids},
    ).mappings().all()

    items = []

    for row in rows:
        item = dict(row)
        item["kickoff_time"] = _candidate_kickoff_time(item)
        items.append(
            {
                "prediction_id": item.get("prediction_id"),
                "match_id": item.get("match_id"),
                "league": item.get("league"),
                "home_team": item.get("home_team"),
                "away_team": item.get("away_team"),
                "kickoff_time": item.get("kickoff_time"),
                "market": item.get("market"),
                "predicted_label": item.get("predicted_label"),
                "odds": item.get("odds"),
                "confidence": item.get("confidence"),
                "value_score": item.get("value_score"),
                "bookmaker": item.get("odds_bookmaker"),
                "odds_match_quality": item.get("odds_match_quality"),
            }
        )

    return sorted(
        items,
        key=lambda item: (
            str(item.get("kickoff_time") or ""),
            int(item.get("prediction_id") or 0),
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

        family = parse_executable_market(candidate.market).family

        if family in used_families:
            continue

        if candidate.odds is None:
            continue

        if candidate.odds < 1.30 or candidate.odds > 4.20:
            continue

        if candidate.value_score is None or candidate.value_score < STRICT_GROUPING_MIN_VALUE_SCORE:
            continue

        if candidate.confidence < STRICT_GROUPING_MIN_CONFIDENCE:
            continue

        test_group = selected + [candidate]
        test_odds = _cumulative_odds(test_group)

        if test_odds is None:
            continue

        if test_odds > max_group_odds:
            continue

        selected.append(candidate)
        used_match_ids.add(candidate.match_id)
        used_markets.add(candidate.market)
        used_families.add(family)

        if len(selected) >= min_group_size and test_odds >= min_group_odds:
            return selected

        if len(selected) >= max_group_size:
            break

    final_odds = _cumulative_odds(selected)

    if (
        len(selected) >= min_group_size
        and final_odds is not None
        and min_group_odds <= final_odds <= max_group_odds
    ):
        return selected

    return []


def _fallback_ranking_score(prediction: Prediction) -> float:
    value_score = prediction.value_score or 0.0
    confidence = prediction.confidence or 0.0
    odds = prediction.odds or 0.0

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

    return confidence * 0.50 + value_score * 0.45 + odds_component


def _cumulative_odds(predictions: list[Prediction]) -> float | None:
    odds_values = [p.odds for p in predictions if p.odds is not None]

    if len(odds_values) != len(predictions):
        return None

    return float(prod(odds_values))