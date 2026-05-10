# backend/app/grouping/create_groups.py

from __future__ import annotations

from dataclasses import dataclass
from math import prod
from statistics import mean
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

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
from app.intelligence.correlation_rules import (
    evaluate_group_correlation,
)
from app.intelligence.portfolio_filters import evaluate_pick_for_portfolio
from app.intelligence.stake_engine import resolve_group_tier
from app.odds.market_quality_engine import get_enabled_markets


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
    max_groups: int = 10
    min_group_size: int = 4
    max_group_size: int = 5

    min_confidence: float = 0.60
    min_value_score: float = 0.00

    min_odds: float = 1.25
    max_odds: float = 3.50

    min_market_roi: float = 0.00
    min_league_roi: float = -0.15
    min_band_roi: float = -0.15

    min_sample_size: int = 10

    max_same_market_per_group: int = 2
    max_same_league_per_group: int = 2

    use_intelligence_filters: bool = True


def group_predictions(
    session: Session,
    slate: str,
    min_confidence: float = 0.52,
    min_group_odds: float = 3.0,
    require_odds: bool = False,
    use_intelligence_filters: bool = True,
    profile: str | None = None,
) -> dict[str, dict[str, float | str]]:
    from app.backtest.portfolio_profiles import PROFILE_CONFIGS

    profile_config = None

    if profile in AUTO_PROFILE_LADDERS:
        for candidate_profile in AUTO_PROFILE_LADDERS[profile]:
            result = group_predictions(
                session=session,
                slate=slate,
                min_confidence=min_confidence,
                min_group_odds=min_group_odds,
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
                "reason": "No approved profile produced a valid group.",
            }
        }

    if profile:
        profile_config = PROFILE_CONFIGS.get(profile)

        if profile_config is None:
            raise ValueError(
                f"Unknown profile: {profile}"
            )

        min_confidence = float(profile_config["min_confidence"])

    config = PortfolioGroupConfig(
        min_confidence=max(min_confidence, 0.50),
        min_sample_size=10,
        use_intelligence_filters=use_intelligence_filters,
        max_odds=(
            float(profile_config["max_odds"])
            if profile_config
            else 3.50
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

        return _summarize_portfolio_groups(portfolio_groups)

    if profile:
        return {
            "message": {
                "status": "no_profile_qualified_groups",
                "profile": profile,
                "reason": "No picks passed portfolio profile filters.",
            }
        }

    print("[PORTFOLIO DEBUG] No profitability portfolio created. Falling back.")

    return _fallback_confidence_groups(
        session=session,
        slate=slate,
        min_confidence=min_confidence,
        min_group_odds=min_group_odds,
        require_odds=require_odds,
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

    print(
        "[PORTFOLIO DEBUG]",
        f"market_intel={len(market_intel)}",
        f"league_market_intel={len(league_market_intel)}",
        f"odds_band_intel={len(odds_band_intel)}",
        f"confidence_band_intel={len(confidence_band_intel)}",
        f"use_intelligence_filters={config.use_intelligence_filters}",
    )

    if not market_intel:
        print("[PORTFOLIO DEBUG] No market intelligence found.")
        return []

    predictions = _load_live_prediction_candidates(
        session=session,
        slate=slate,
        min_confidence=config.min_confidence,
        require_odds=require_odds,
    )

    print(
        "[PORTFOLIO DEBUG]",
        f"live_candidates={len(predictions)}",
        f"require_odds={require_odds}",
        f"min_confidence={config.min_confidence}",
    )

    best_by_match: dict[int, dict[str, Any]] = {}
    rejected_by_filter = 0

    for prediction in predictions:
        enriched = _enrich_candidate(
            session=session,
            prediction=prediction,
            market_intel=market_intel,
            league_market_intel=league_market_intel,
            odds_band_intel=odds_band_intel,
            confidence_band_intel=confidence_band_intel,
            config=config,
        )

        if enriched is None:
            rejected_by_filter += 1
            continue

        match_id = int(enriched["match_id"])
        current_best = best_by_match.get(match_id)

        if current_best is None:
            best_by_match[match_id] = enriched
            continue

        if enriched["selection_score"] > current_best["selection_score"]:
            best_by_match[match_id] = enriched

    enriched_candidates = sorted(
        best_by_match.values(),
        key=lambda item: (
            item.get("portfolio_tier") == "AGGRESSIVE",
            -float(item["selection_score"]),
            float(item.get("portfolio_risk_score") or 0.0),
            -float(item["confidence"]),
            item["prediction_id"],
        ),
    )

    print(
        "[PORTFOLIO DEBUG]",
        f"enriched_unique_matches={len(enriched_candidates)}",
        f"rejected_by_filter={rejected_by_filter}",
        f"min_group_size={config.min_group_size}",
    )

    if len(enriched_candidates) < config.min_group_size:
        return []

    groups = _construct_diversified_groups(
        candidates=enriched_candidates,
        config=config,
    )

    print(
        "[PORTFOLIO DEBUG]",
        f"portfolio_groups_created={len(groups)}",
    )

    return groups


def _load_live_prediction_candidates(
    session: Session,
    slate: str,
    min_confidence: float,
    require_odds: bool,
) -> list[dict[str, Any]]:
    enabled_markets = get_enabled_markets(session)

    if not enabled_markets:
        print("[MARKET QUALITY] No enabled markets found.")
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
            p.model_name,
            m.league,
            m.home_team,
            m.away_team,
            m.kickoff_date
        FROM predictions p
        JOIN matches m
            ON m.id = p.match_id
        WHERE p.slate = :slate
          AND p.confidence >= :min_confidence
          AND p.market = ANY(:enabled_markets)
          {odds_filter}
        ORDER BY p.confidence DESC, p.id ASC
        """
    )

    rows = session.execute(
        query,
        {
            "slate": slate,
            "min_confidence": min_confidence,
            "enabled_markets": enabled_markets,
        },
    ).fetchall()

    return [dict(row._mapping) for row in rows]


def _enrich_candidate(
    session: Session,
    prediction: dict[str, Any],
    market_intel: dict[str, dict[str, Any]],
    league_market_intel: dict[tuple[str, str], dict[str, Any]],
    odds_band_intel: dict[tuple[str, str], dict[str, Any]],
    confidence_band_intel: dict[tuple[str, str], dict[str, Any]],
    config: PortfolioGroupConfig,
) -> dict[str, Any] | None:
    market = prediction["market"]
    league = prediction.get("league") or "unknown"

    enabled_markets = set(get_enabled_markets(session))

    if market not in enabled_markets:
        print("[FILTER] market quality disabled", market)
        return None

    confidence = float(prediction["confidence"] or 0.0)
    value_score = float(prediction["value_score"] or 0.0)
    odds = prediction.get("odds")

    if odds is not None:
        odds = float(odds)

    if config.use_intelligence_filters:
        filter_result = evaluate_pick_for_portfolio(
            session=session,
            league=league,
            market=market,
            confidence=confidence,
            odds=odds,
            value_score=value_score,
            strict=True,
        )

        prediction["portfolio_allowed"] = filter_result.allowed
        prediction["portfolio_filter_reason"] = filter_result.reason
        prediction["portfolio_risk_flags"] = filter_result.risk_flags
        prediction["portfolio_risk_score"] = filter_result.risk_score
        prediction["portfolio_tier"] = filter_result.tier

        if not filter_result.allowed:
            print(
                "[INTELLIGENCE FILTER]",
                market,
                league,
                f"confidence={round(confidence, 4)}",
                f"odds={odds}",
                f"value={round(value_score, 4)}",
                filter_result.reason,
                filter_result.risk_flags,
                f"risk={round(filter_result.risk_score, 2)}",
            )
            return None
    else:
        prediction["portfolio_allowed"] = True
        prediction["portfolio_filter_reason"] = "Not used"
        prediction["portfolio_risk_flags"] = []
        prediction["portfolio_risk_score"] = 0.0

    if market not in market_intel:
        print("[FILTER] no market intel", market)
        return None

    if value_score < config.min_value_score:
        print("[FILTER] low value score", market, value_score)
        return None

    if odds is not None:
        if odds < config.min_odds or odds > config.max_odds:
            print("[FILTER] odds out of range", market, odds)
            return None

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
        print("[FILTER] negative market roi", market, market_roi)
        return None

    if league_sample_size >= config.min_sample_size and league_roi < config.min_league_roi:
        print("[FILTER] weak league roi", league, market, league_roi, league_sample_size)
        return None

    if odds_band_sample_size >= config.min_sample_size and odds_band_roi < config.min_band_roi:
        print("[FILTER] weak odds band", market, odds_band(odds), odds_band_roi, odds_band_sample_size)
        return None

    if confidence_band_sample_size >= config.min_sample_size and confidence_band_roi < config.min_band_roi:
        print(
            "[FILTER] weak confidence band",
            market,
            confidence_band(confidence),
            confidence_band_roi,
            confidence_band_sample_size,
        )
        return None

    sample_penalty = _sample_penalty(
        market_sample_size=market_sample_size,
        league_sample_size=league_sample_size,
        odds_band_sample_size=odds_band_sample_size,
        confidence_band_sample_size=confidence_band_sample_size,
        min_sample_size=config.min_sample_size,
    )

    odds_quality = 0.0

    if odds is not None:
        odds_quality = min(odds / 5.0, 0.50)

    risk_penalty = max(float(prediction.get("portfolio_risk_score") or 0.0), 0.0) / 100.0

    selection_score = (
        confidence * 0.25
        + value_score * 0.20
        + market_roi * 0.20
        + league_roi * 0.15
        + odds_band_roi * 0.10
        + confidence_band_roi * 0.10
        + odds_quality * 0.05
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
    prediction["selection_score"] = selection_score

    print(
        "[PORTFOLIO ACCEPTED]",
        market,
        league,
        f"confidence={round(confidence, 4)}",
        f"odds={odds}",
        f"value={round(value_score, 4)}",
        f"market_roi={round(market_roi, 4)}",
        f"league_roi={round(league_roi, 4)}",
        f"odds_band_roi={round(odds_band_roi, 4)}",
        f"confidence_band_roi={round(confidence_band_roi, 4)}",
        f"risk={round(float(prediction.get('portfolio_risk_score') or 0.0), 2)}",
        f"score={round(selection_score, 4)}",
    )

    return prediction


def _sample_penalty(
    market_sample_size: int,
    league_sample_size: int,
    odds_band_sample_size: int,
    confidence_band_sample_size: int,
    min_sample_size: int,
) -> float:
    penalty = 0.0

    if market_sample_size < min_sample_size * 2:
        penalty += 0.03

    if league_sample_size == 0:
        penalty += 0.05
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

    for _ in range(config.max_groups):
        group: list[dict[str, Any]] = []

        for candidate in candidates:
            match_id = int(candidate["match_id"])

            if match_id in used_match_ids:
                continue

            if not _candidate_fits_group(candidate, group, config):
                continue

            group.append(candidate)
            used_match_ids.add(match_id)

            if len(group) >= config.max_group_size:
                break

        if len(group) >= config.min_group_size:
            groups.append(group)
        else:
            for item in group:
                used_match_ids.discard(int(item["match_id"]))
            break

    return groups


def _candidate_fits_group(
    candidate: dict[str, Any],
    group: list[dict[str, Any]],
    config: PortfolioGroupConfig,
) -> bool:
    market = candidate["market"]
    league = candidate.get("league") or "unknown"

    same_market_count = sum(
        1
        for item in group
        if item["market"] == market
    )

    same_league_count = sum(
        1
        for item in group
        if (item.get("league") or "unknown") == league
    )

    if same_market_count >= config.max_same_market_per_group:
        return False

    if same_league_count >= config.max_same_league_per_group:
        return False

    correlation = evaluate_group_correlation(
        existing_group=group,
        candidate=candidate,
    )

    candidate["correlation_score"] = correlation.correlation_score
    candidate["correlation_reasons"] = correlation.reasons

    if not correlation.allowed:
        print(
            "[CORRELATION BLOCKED]",
            candidate["market"],
            candidate.get("league"),
            correlation.correlation_score,
            correlation.reasons,
        )

        return False

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
            "odds_coverage": round(len(odds_values) / len(group), 4),
        }

    return summaries


def _fallback_confidence_groups(
    session: Session,
    slate: str,
    min_confidence: float = 0.65,
    min_group_odds: float = 3.0,
    require_odds: bool = False,
) -> dict[str, dict[str, float | str]]:
    enabled_markets = set(get_enabled_markets(session))

    query = (
        select(Prediction)
        .where(
            Prediction.slate == slate,
            Prediction.confidence >= min_confidence,
            Prediction.market.in_(enabled_markets),
        )
        .order_by(
            Prediction.confidence.desc(),
            Prediction.id.asc(),
        )
    )

    if require_odds:
        query = query.where(Prediction.odds.isnot(None))

    predictions = list(session.scalars(query))

    best_prediction_by_match: dict[int, Prediction] = {}

    for prediction in predictions:
        current_best = best_prediction_by_match.get(prediction.match_id)

        if current_best is None:
            best_prediction_by_match[prediction.match_id] = prediction
            continue

        if _fallback_ranking_score(prediction) > _fallback_ranking_score(current_best):
            best_prediction_by_match[prediction.match_id] = prediction

    ranked_games = sorted(
        best_prediction_by_match.values(),
        key=lambda prediction: (
            -_fallback_ranking_score(prediction),
            prediction.id,
        ),
    )

    if len(ranked_games) < 4:
        return {
            "message": {
                "status": "not_enough_predictions",
                "available_games": float(len(ranked_games)),
            }
        }

    group_sizes = _group_sizes(
        total_games=len(ranked_games),
        max_groups=10,
        min_group_size=4,
        max_group_size=5,
    )

    session.execute(
        delete(PredictionGroupItem).where(
            PredictionGroupItem.slate == slate,
        )
    )

    group_summaries: dict[str, dict[str, float | str]] = {}
    remaining_games = ranked_games.copy()

    for group_number, size in enumerate(group_sizes, start=1):
        group_name = f"Group {group_number}"

        selected_games: list[Prediction] = []
        selected_match_ids: set[int] = set()

        for candidate in remaining_games:
            if candidate.match_id in selected_match_ids:
                continue

            selected_games.append(candidate)
            selected_match_ids.add(candidate.match_id)

            if len(selected_games) >= size:
                break

        if len(selected_games) < 4:
            break

        remaining_games = [
            candidate
            for candidate in remaining_games
            if candidate.match_id not in selected_match_ids
        ]

        odds_available = all(
            prediction.odds is not None
            for prediction in selected_games
        )

        cumulative_odds = _cumulative_odds(selected_games)

        if (
            require_odds
            and cumulative_odds is not None
            and cumulative_odds < min_group_odds
        ):
            boosted_games = _boost_group_to_min_odds(
                selected_games=selected_games,
                available_games=remaining_games,
                min_group_odds=min_group_odds,
            )

            boosted_match_ids = {game.match_id for game in boosted_games}

            if len(boosted_match_ids) == len(boosted_games):
                selected_games = boosted_games
                selected_match_ids = boosted_match_ids

                remaining_games = [
                    candidate
                    for candidate in remaining_games
                    if candidate.match_id not in selected_match_ids
                ]

                cumulative_odds = _cumulative_odds(selected_games)

        for prediction in selected_games:
            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=prediction.id,
                )
            )

        group_type = (
            "FALLBACK_VALUE_GROUP"
            if odds_available
            else "FALLBACK_CONFIDENCE_GROUP"
        )

        group_summaries[group_name] = {
            "group_type": group_type,
            "average_confidence": round(mean([p.confidence for p in selected_games]), 4),
            "cumulative_odds": round(cumulative_odds, 4) if cumulative_odds is not None else 0.0,
            "games": float(len(selected_games)),
            "odds_coverage": round(
                sum(1 for p in selected_games if p.odds is not None) / len(selected_games),
                4,
            ),
        }

    session.commit()

    return group_summaries


def _fallback_ranking_score(prediction: Prediction) -> float:
    value_score = prediction.value_score or 0.0
    odds_bonus = 0.0

    if prediction.odds:
        odds_bonus = min(prediction.odds / 10, 0.25)

    return prediction.confidence + value_score + odds_bonus


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

    return float(prod(odds_values))


def _boost_group_to_min_odds(
    selected_games: list[Prediction],
    available_games: list[Prediction],
    min_group_odds: float,
) -> list[Prediction]:
    selected_ids = {
        p.id
        for p in selected_games
    }

    candidates = [
        p
        for p in available_games
        if p.id not in selected_ids
        and p.odds is not None
    ]

    current = selected_games[:]

    for i in range(len(current)):
        best_replacement = None
        best_odds = _cumulative_odds(current) or 0.0

        for candidate in candidates:
            test_group = current[:]
            test_group[i] = candidate

            test_odds = _cumulative_odds(test_group) or 0.0

            if test_odds > best_odds:
                best_odds = test_odds
                best_replacement = candidate

        if best_replacement:
            current[i] = best_replacement

        final_odds = _cumulative_odds(current)

        if final_odds and final_odds >= min_group_odds:
            break

    return current


def _group_sizes(
    total_games: int,
    max_groups: int = 10,
    min_group_size: int = 4,
    max_group_size: int = 5,
) -> list[int]:
    usable_games = min(
        total_games,
        max_groups * max_group_size,
    )

    group_count = max(
        1,
        usable_games // min_group_size,
    )

    sizes = [
        min_group_size
        for _ in range(group_count)
    ]

    remaining = usable_games - (
        group_count * min_group_size
    )

    index = 0

    while remaining > 0 and index < group_count:
        if sizes[index] < max_group_size:
            sizes[index] += 1
            remaining -= 1

        index += 1

    return sizes