# backend/app/analysis/live_rejection_report.py

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.backtest.portfolio_profiles import PROFILE_CONFIGS
from app.db.models import Match, Prediction
from app.intelligence.portfolio_filters import (
    evaluate_pick_for_portfolio,
)
from app.utils.slate import resolve_slate


AUTO_PROFILE_LADDERS = {
    "AUTO_SAFE": [
        "SAFE_B_CURRENT_BEST",
        "SAFE_D_MORE_ROOM",
        "SAFE_C_HIGHER_CONF",
        "BALANCED_REFERENCE",
    ],
}


def _resolve_profile(profile: str | None) -> dict[str, Any]:
    if not profile:
        return {
            "min_confidence": 0.65,
            "max_odds": 3.50,
        }

    if profile in AUTO_PROFILE_LADDERS:
        first_profile = AUTO_PROFILE_LADDERS[profile][0]
        return PROFILE_CONFIGS[first_profile]

    profile_config = PROFILE_CONFIGS.get(profile)

    if not profile_config:
        raise ValueError(f"Unknown profile: {profile}")

    return profile_config


def build_live_rejection_report(
    session: Session,
    slate: str | None = None,
    profile: str | None = None,
    require_odds: bool = True,
):
    selected_slate = resolve_slate(slate)

    profile_config = _resolve_profile(profile)

    min_confidence = float(profile_config["min_confidence"])
    max_odds = float(profile_config["max_odds"])

    query = (
        session.query(Prediction, Match)
        .join(Match, Match.id == Prediction.match_id)
        .filter(Prediction.slate == selected_slate)
    )

    predictions = query.all()

    rejection_reasons = Counter()
    blocked_leagues = Counter()
    blocked_markets = Counter()

    approved = 0
    rejected = 0

    approved_rows = []

    for prediction, match in predictions:
        confidence = float(prediction.confidence or 0)
        odds = (
            float(prediction.odds)
            if prediction.odds is not None
            else None
        )

        value_score = (
            float(prediction.value_score)
            if prediction.value_score is not None
            else None
        )

        if confidence < min_confidence:
            rejection_reasons["below_min_confidence"] += 1
            rejected += 1
            continue

        if require_odds and odds is None:
            rejection_reasons["missing_odds"] += 1
            rejected += 1
            continue

        if odds is not None and odds > max_odds:
            rejection_reasons["odds_above_profile_limit"] += 1
            rejected += 1
            continue

        if value_score is not None and value_score < 0:
            rejection_reasons["negative_value_score"] += 1
            rejected += 1
            continue

        result = evaluate_pick_for_portfolio(
            session=session,
            league=match.league,
            market=prediction.market,
            confidence=confidence,
            odds=odds,
            value_score=value_score,
            strict=True,
        )

        if not result.allowed:
            rejected += 1

            rejection_reasons[result.reason] += 1

            blocked_leagues[match.league or "UNKNOWN"] += 1
            blocked_markets[prediction.market or "UNKNOWN"] += 1

            continue

        approved += 1

        approved_rows.append(
            {
                "league": match.league,
                "market": prediction.market,
                "confidence": confidence,
                "odds": odds,
                "value_score": value_score,
                "home_team": match.home_team,
                "away_team": match.away_team,
            }
        )

    approved_rows = sorted(
        approved_rows,
        key=lambda row: (
            row["confidence"],
            row["value_score"] or 0,
        ),
        reverse=True,
    )

    return {
        "slate": selected_slate,
        "profile": profile,
        "approved_candidates": approved,
        "rejected_candidates": rejected,
        "top_rejection_reasons": dict(
            rejection_reasons.most_common(10)
        ),
        "top_blocked_leagues": dict(
            blocked_leagues.most_common(10)
        ),
        "top_blocked_markets": dict(
            blocked_markets.most_common(10)
        ),
        "best_approved_candidates": approved_rows[:10],
    }