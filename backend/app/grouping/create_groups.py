# backend/app/grouping/create_groups.py

from __future__ import annotations

from dataclasses import dataclass
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
from app.intelligence.stake_engine import resolve_group_tier
from app.odds.market_quality_engine import get_enabled_markets
from app.services.league_production_filter_service import (
    filter_candidate_dicts_by_league_quality,
)
from app.services.production_pick_scoring_service import score_pick_list


GROUPING_DEBUG = False

MAX_RAW_CANDIDATES = 900
MAX_ENRICHMENT_CANDIDATES = 450
MAX_UNIQUE_MATCH_CANDIDATES = 220
MAX_APPROVED_CANDIDATES = 150

MIN_GAMES_PER_GROUP = 2
MAX_GAMES_PER_GROUP = 3
MAX_GROUPS = 6

PRODUCTION_MIN_GROUP_ODDS = 2.0
PRODUCTION_MAX_GROUP_ODDS = 80.0

AUTO_PROFILE_LADDERS = {
    "AUTO_SAFE": [
        "SAFE_B_CURRENT_BEST",
        "SAFE_D_MORE_ROOM",
        "SAFE_C_HIGHER_CONF",
        "BALANCED_REFERENCE",
    ],
}


@dataclass(frozen=True)
class PortfolioGroupConfig:
    max_groups: int = MAX_GROUPS
    min_group_size: int = MIN_GAMES_PER_GROUP
    max_group_size: int = MAX_GAMES_PER_GROUP

    league_odds_filter_mode: str = "strict"

    min_confidence: float = 0.55
    min_value_score: float = 0.00

    min_odds: float = 1.30
    max_odds: float = 4.50

    min_group_odds: float = PRODUCTION_MIN_GROUP_ODDS
    max_group_odds: float = PRODUCTION_MAX_GROUP_ODDS

    min_market_roi: float = -0.20
    min_league_roi: float = -0.25
    min_band_roi: float = -0.25

    max_same_family_per_group: int = 2
    min_sample_size: int = 10

    max_same_market_per_group: int = 1
    max_same_league_per_group: int = 2

    use_intelligence_filters: bool = True


def _debug(*args: Any) -> None:
    if GROUPING_DEBUG:
        print(*args)


def group_predictions(
    session: Session,
    slate: str,
    min_confidence: float = 0.55,
    min_group_odds: float = PRODUCTION_MIN_GROUP_ODDS,
    require_odds: bool = True,
    use_intelligence_filters: bool = True,
    profile: str | None = None,
    league_odds_filter_mode: str = "strict",
) -> dict[str, dict[str, float | str]]:
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
                "reason": "No approved profile produced a valid production-safe group.",
            }
        }

    if profile:
        profile_config = PROFILE_CONFIGS.get(profile)

        if profile_config is None:
            raise ValueError(f"Unknown profile: {profile}")

        min_confidence = float(profile_config["min_confidence"])

    config = PortfolioGroupConfig(
        min_confidence=max(float(min_confidence), 0.55),
        min_group_odds=max(float(min_group_odds), PRODUCTION_MIN_GROUP_ODDS),
        max_group_odds=PRODUCTION_MAX_GROUP_ODDS,
        min_sample_size=10,
        use_intelligence_filters=use_intelligence_filters,
        league_odds_filter_mode=league_odds_filter_mode,
        max_odds=(
            min(float(profile_config["max_odds"]), 4.50)
            if profile_config
            else 4.50
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
                "reason": "No picks passed production-safe portfolio filters.",
            }
        }

    return _fallback_confidence_groups(
        session=session,
        slate=slate,
        min_confidence=min_confidence,
        min_group_odds=config.min_group_odds,
        max_group_odds=config.max_group_odds,
        require_odds=require_odds,
        league_odds_filter_mode=league_odds_filter_mode,
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
        return []

    predictions = _load_live_prediction_candidates(
        session=session,
        slate=slate,
        min_confidence=config.min_confidence,
        require_odds=require_odds,
        enabled_markets=enabled_markets,
        max_candidates=MAX_RAW_CANDIDATES,
    )

    predictions = _prefer_best_odds_candidates(predictions)
    predictions = predictions[:MAX_ENRICHMENT_CANDIDATES]

    predictions, _league_rejections = filter_candidate_dicts_by_league_quality(
        session=session,
        candidates=predictions,
        mode=config.league_odds_filter_mode,
    )

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

    enriched_candidates = sorted(
        best_by_match.values(),
        key=lambda item: (
            item.get("portfolio_tier") == "AGGRESSIVE",
            -float(item["selection_score"]),
            -float(item.get("odds_match_quality_score") or 0.0),
            float(item.get("portfolio_risk_score") or 0.0),
            -float(item["confidence"]),
            item["prediction_id"],
        ),
    )[:MAX_UNIQUE_MATCH_CANDIDATES]

    if len(enriched_candidates) < config.min_group_size:
        return []

    scored_candidates = score_pick_list(enriched_candidates)

    exposure_result = apply_exposure_controls(
        picks=scored_candidates,
        max_per_league=config.max_same_league_per_group,
        max_per_market=config.max_same_market_per_group,
        max_per_market_family=config.max_same_family_per_group,
    )

    recommendation_layer = build_recommendation_layer(
        exposure_result=exposure_result,
    )

    approved_candidates = [
        pick
        for pick in recommendation_layer["approved_picks"]
        if pick.get("risk_level") != "AVOID"
        and float(pick.get("production_score") or 0.0) >= 70.0
    ][:MAX_APPROVED_CANDIDATES]

    if len(approved_candidates) < config.min_group_size:
        return []

    return _construct_diversified_groups(
        candidates=approved_candidates,
        config=config,
    )


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
            m.league,
            m.home_team,
            m.away_team,
            m.kickoff_date
        FROM predictions p
        JOIN matches m ON m.id = p.match_id
        WHERE p.slate = :slate
          AND p.confidence >= :min_confidence
          AND p.market = ANY(:enabled_markets)
          {odds_filter}
        ORDER BY
            CASE
                WHEN p.odds_match_quality = 'exact_canonical' THEN 5
                WHEN p.odds_match_quality = 'exact_market_fallback' THEN 4
                WHEN p.odds_match_quality IN (
                    'goal_total',
                    'team_total',
                    'corners',
                    'shots_on_target',
                    'first_half',
                    'asian_handicap'
                ) THEN 3
                WHEN p.odds_match_quality = 'direct' THEN 2
                ELSE 1
            END DESC,
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
            "enabled_markets": list(enabled_markets),
            "max_candidates": int(max_candidates),
        },
    ).fetchall()

    return [dict(row._mapping) for row in rows]


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
        "exact_canonical": 100.0,
        "exact_market_fallback": 85.0,
        "goal_total": 72.0,
        "team_total": 72.0,
        "corners": 70.0,
        "shots_on_target": 70.0,
        "first_half": 68.0,
        "asian_handicap": 68.0,
        "direct": 55.0,
    }.get(str(quality), 20.0)

    odds_points = 0.0

    if odds is not None:
        selected_odds = float(odds)

        if 1.30 <= selected_odds <= 2.50:
            odds_points += 12.0
        elif 2.50 < selected_odds <= 3.50:
            odds_points += 6.0
        elif selected_odds > 4.50:
            odds_points -= 18.0
        elif selected_odds < 1.30:
            odds_points -= 30.0

    bookmaker_points = 8.0 if prediction.get("odds_bookmaker") else 0.0

    return round(
        quality_points
        + bookmaker_points
        + min(value_score * 80.0, 20.0)
        + min(confidence * 10.0, 10.0)
        + odds_points,
        4,
    )


def _best_grouping_pick_score(prediction: dict[str, Any]) -> float:
    return round(
        float(prediction.get("selection_score") or 0.0)
        + (_best_odds_quality_score(prediction) / 1000.0)
        - (float(prediction.get("portfolio_risk_score") or 0.0) / 1000.0),
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

    if market not in enabled_markets:
        return None

    confidence = float(prediction["confidence"] or 0.0)
    value_score = float(prediction["value_score"] or 0.0)
    odds = prediction.get("odds")

    if odds is None:
        return None

    odds = float(odds)

    if value_score < config.min_value_score:
        return None

    if odds < config.min_odds or odds > config.max_odds:
        return None

    if market not in market_intel:
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

    market_data = market_intel[market]
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

    if market_roi < config.min_market_roi:
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
    )

    odds_quality = _odds_quality_component(odds)

    risk_penalty = max(
        float(prediction.get("portfolio_risk_score") or 0.0),
        0.0,
    ) / 140.0

    bookmaker = prediction.get("odds_bookmaker")
    odds_match_quality = prediction.get("odds_match_quality") or "none"
    odds_match_quality_score = _best_odds_quality_score(prediction)
    bookmaker_execution_score = odds_match_quality_score / 100.0

    selection_score = (
        confidence * 0.26
        + value_score * 0.28
        + market_roi * 0.14
        + league_roi * 0.10
        + odds_band_roi * 0.08
        + confidence_band_roi * 0.08
        + odds_quality * 0.08
        + bookmaker_execution_score * 0.10
        - sample_penalty
        - risk_penalty
    )

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
    prediction["odds_bookmaker"] = bookmaker
    prediction["odds_match_quality"] = odds_match_quality
    prediction["selection_score"] = selection_score

    return prediction


def _odds_quality_component(odds: float) -> float:
    if odds < 1.30:
        return -0.40

    if odds <= 1.80:
        return 0.25

    if odds <= 2.50:
        return 0.50

    if odds <= 3.50:
        return 0.30

    if odds <= 4.50:
        return 0.05

    return -0.50


def _sample_penalty(
    market_sample_size: int,
    league_sample_size: int,
    odds_band_sample_size: int,
    confidence_band_sample_size: int,
    min_sample_size: int,
) -> float:
    penalty = 0.0

    if market_sample_size < min_sample_size * 2:
        penalty += 0.02

    if league_sample_size == 0:
        penalty += 0.03
    elif league_sample_size < min_sample_size:
        penalty += 0.02

    if odds_band_sample_size == 0:
        penalty += 0.02

    if confidence_band_sample_size == 0:
        penalty += 0.02

    return penalty


def _construct_diversified_groups(
    candidates: list[dict[str, Any]],
    config: PortfolioGroupConfig,
) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    used_match_ids: set[int] = set()

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

    if cumulative < min_group_odds:
        return False

    if cumulative > max_group_odds:
        return False

    return True


def _candidate_fits_group(
    candidate: dict[str, Any],
    group: list[dict[str, Any]],
    config: PortfolioGroupConfig,
) -> bool:
    market = candidate["market"]
    league = candidate.get("league") or "unknown"
    market_family = candidate.get("market_family") or _resolve_group_market_family(market)

    same_market_count = sum(1 for item in group if item["market"] == market)
    same_league_count = sum(
        1
        for item in group
        if (item.get("league") or "unknown") == league
    )
    same_family_count = sum(
        1
        for item in group
        if (item.get("market_family") or _resolve_group_market_family(item["market"]))
        == market_family
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
    if (
        "over" in market
        or "under" in market
        or "btts" in market
        or "goal" in market
        or "score" in market
    ):
        return "GOALS"

    if "handicap" in market:
        return "HANDICAP"

    if (
        "win" in market
        or "draw" in market
        or "chance" in market
        or "ht_ft" in market
    ):
        return "RESULT"

    if "corner" in market:
        return "CORNERS"

    if "shot" in market:
        return "SHOTS"

    return "OTHER"


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
) -> dict[str, dict[str, float | str]]:
    summaries: dict[str, dict[str, float | str]] = {}

    for group_index, group in enumerate(groups, start=1):
        group_name = f"Portfolio Group {group_index}"

        odds_values = [
            float(item["odds"])
            for item in group
            if item.get("odds") is not None
        ]

        risk_scores = [
            float(item.get("portfolio_risk_score") or 0.0)
            for item in group
        ]

        average_risk_score = mean(risk_scores) if risk_scores else 0.0
        max_risk_score = max(risk_scores) if risk_scores else 0.0

        group_tier = resolve_group_tier(
            average_risk_score=average_risk_score,
            max_risk_score=max_risk_score,
        )

        cumulative_odds = (
            float(prod(odds_values))
            if len(odds_values) == len(group)
            else 0.0
        )

        if cumulative_odds > config.max_group_odds:
            group_tier = "REJECTED"

        summaries[group_name] = {
            "group_type": "PROFITABILITY_PORTFOLIO",
            "group_tier": group_tier,
            "games": float(len(group)),
            "average_confidence": round(mean(float(item["confidence"] or 0.0) for item in group), 4),
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
        }

    return summaries


def _fallback_confidence_groups(
    session: Session,
    slate: str,
    min_confidence: float = 0.65,
    min_group_odds: float = PRODUCTION_MIN_GROUP_ODDS,
    max_group_odds: float = PRODUCTION_MAX_GROUP_ODDS,
    require_odds: bool = True,
    league_odds_filter_mode: str = "strict",
) -> dict[str, dict[str, float | str]]:
    enabled_markets = set(get_enabled_markets(session))

    query = (
        select(Prediction)
        .where(
            Prediction.slate == slate,
            Prediction.confidence >= max(min_confidence, 0.55),
            Prediction.market.in_(enabled_markets),
            Prediction.value_score.isnot(None),
            Prediction.value_score >= 0.0,
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
            Prediction.odds <= 4.50,
        )

    predictions = list(session.scalars(query))

    candidate_dicts = [
        {
            "prediction_id": prediction.id,
            "match_id": prediction.match_id,
            "league": None,
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
                m.league
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.slate = :slate
            """
        ),
        {"slate": slate},
    ).mappings().all()

    league_by_prediction_id = {
        int(row["prediction_id"]): row["league"]
        for row in league_map_rows
    }

    for item in candidate_dicts:
        item["league"] = league_by_prediction_id.get(int(item["prediction_id"]))

    approved_dicts, _league_rejections = filter_candidate_dicts_by_league_quality(
        session=session,
        candidates=candidate_dicts,
        mode=league_odds_filter_mode,
    )

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
                "reason": "Not enough positive-value odds-backed predictions passed fallback production filters.",
            }
        }

    session.execute(
        delete(PredictionGroupItem).where(
            PredictionGroupItem.slate == slate,
        )
    )

    group_summaries: dict[str, dict[str, float | str]] = {}
    remaining_games = ranked_games.copy()

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

        odds_available = all(
            prediction.odds is not None
            for prediction in selected_games
        )

        for prediction in selected_games:
            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=prediction.id,
                )
            )

        group_summaries[group_name] = {
            "group_type": "FALLBACK_VALUE_GROUP_PRODUCTION_SAFE",
            "average_confidence": round(mean([p.confidence for p in selected_games]), 4),
            "average_value_score": round(mean([(p.value_score or 0.0) for p in selected_games]), 4),
            "cumulative_odds": round(cumulative_odds, 4),
            "min_group_odds": round(min_group_odds, 4),
            "max_group_odds": round(max_group_odds, 4),
            "games": float(len(selected_games)),
            "odds_coverage": round(
                sum(1 for p in selected_games if p.odds is not None) / len(selected_games),
                4,
            ),
            "group_tier": "FALLBACK_SAFE" if odds_available else "FALLBACK_REJECTED",
        }

    session.commit()

    if not group_summaries:
        return {
            "message": {
                "status": "no_safe_fallback_groups",
                "reason": "Predictions existed, but no fallback groups fit production odds limits.",
                "min_group_odds": float(min_group_odds),
                "max_group_odds": float(max_group_odds),
            }
        }

    return group_summaries


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

    for candidate in available_games:
        if candidate.match_id in used_match_ids:
            continue

        if candidate.market in used_markets:
            continue

        if candidate.odds is None:
            continue

        if candidate.odds < 1.30 or candidate.odds > 4.50:
            continue

        if candidate.value_score is None or candidate.value_score < 0:
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
        odds_component = 0.08
    elif 1.80 < odds <= 2.50:
        odds_component = 0.12
    elif 2.50 < odds <= 3.50:
        odds_component = 0.06
    elif odds > 3.50:
        odds_component = -0.06
    elif 0 < odds < 1.30:
        odds_component = -0.20

    return (
        confidence * 0.45
        + value_score * 0.45
        + odds_component
    )


def _cumulative_odds(predictions: list[Prediction]) -> float | None:
    odds_values = [
        p.odds
        for p in predictions
        if p.odds is not None
    ]

    if len(odds_values) != len(predictions):
        return None

    return float(prod(odds_values))


def _boost_group_to_min_odds(
    selected_games: list[Prediction],
    available_games: list[Prediction],
    min_group_odds: float,
    max_group_odds: float = PRODUCTION_MAX_GROUP_ODDS,
) -> list[Prediction]:
    selected_ids = {p.id for p in selected_games}

    candidates = [
        p
        for p in available_games
        if p.id not in selected_ids
        and p.odds is not None
        and p.value_score is not None
        and p.value_score >= 0.0
        and 1.30 <= p.odds <= 4.50
    ]

    current = selected_games[:]

    for i in range(len(current)):
        best_replacement = None
        best_score = _fallback_group_score(current)

        for candidate in candidates:
            test_group = current[:]
            test_group[i] = candidate

            test_odds = _cumulative_odds(test_group)

            if test_odds is None:
                continue

            if test_odds > max_group_odds:
                continue

            if test_odds < min_group_odds:
                continue

            test_score = _fallback_group_score(test_group)

            if test_score > best_score:
                best_score = test_score
                best_replacement = candidate

        if best_replacement:
            current[i] = best_replacement

        final_odds = _cumulative_odds(current)

        if final_odds and min_group_odds <= final_odds <= max_group_odds:
            break

    return current


def _fallback_group_score(group: list[Prediction]) -> float:
    if not group:
        return 0.0

    odds_value = _cumulative_odds(group) or 0.0

    if odds_value > PRODUCTION_MAX_GROUP_ODDS:
        return -999.0

    return round(
        mean([float(p.confidence or 0.0) for p in group]) * 0.45
        + mean([float(p.value_score or 0.0) for p in group]) * 0.45
        - max((odds_value - 20.0) / 200.0, 0.0),
        6,
    )


def _group_sizes(
    total_games: int,
    max_groups: int = MAX_GROUPS,
    min_group_size: int = MIN_GAMES_PER_GROUP,
    max_group_size: int = MAX_GAMES_PER_GROUP,
) -> list[int]:
    usable_games = min(
        total_games,
        max_groups * max_group_size,
    )

    if usable_games < min_group_size:
        return []

    sizes: list[int] = []

    remaining = usable_games

    while remaining >= min_group_size and len(sizes) < max_groups:
        size = min(max_group_size, remaining)

        if remaining - size > 0 and remaining - size < min_group_size:
            size = remaining

        sizes.append(size)
        remaining -= size

    return sizes