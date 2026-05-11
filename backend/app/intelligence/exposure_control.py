# backend/app/intelligence/exposure_control.py

from __future__ import annotations

from collections import defaultdict
from typing import Any


MARKET_FAMILY_MAP = {
    "home_win": "MATCH_RESULT",
    "away_win": "MATCH_RESULT",
    "draw": "MATCH_RESULT",

    "double_chance_1x": "DOUBLE_CHANCE",
    "double_chance_x2": "DOUBLE_CHANCE",
    "double_chance_12": "DOUBLE_CHANCE",

    "over_1_5_goals": "GOALS",
    "under_1_5_goals": "GOALS",
    "over_2_5_goals": "GOALS",
    "under_2_5_goals": "GOALS",
    "over_3_5_goals": "GOALS",
    "under_3_5_goals": "GOALS",

    "btts_yes": "BTTS",
    "btts_no": "BTTS",

    "corners_over_8_5": "CORNERS",
    "corners_under_8_5": "CORNERS",

    "shots_on_target_over_8_5": "SHOTS_ON_TARGET",
    "shots_on_target_under_8_5": "SHOTS_ON_TARGET",
}


def get_market_family(market: str | None) -> str:
    if not market:
        return "UNKNOWN"

    return MARKET_FAMILY_MAP.get(
        market,
        "OTHER",
    )


def apply_exposure_controls(
    picks: list[dict[str, Any]],
    max_per_league: int = 3,
    max_per_market: int = 5,
    max_per_market_family: int = 6,
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    league_counts: dict[str, int] = defaultdict(int)
    market_counts: dict[str, int] = defaultdict(int)
    family_counts: dict[str, int] = defaultdict(int)

    sorted_picks = sorted(
        picks,
        key=lambda item: item.get("production_score", 0),
        reverse=True,
    )

    for pick in sorted_picks:
        league = pick.get("league") or "UNKNOWN"
        market = pick.get("market") or "UNKNOWN"

        family = get_market_family(market)

        rejection_reasons: list[str] = []

        if league_counts[league] >= max_per_league:
            rejection_reasons.append(
                "league exposure exceeded"
            )

        if market_counts[market] >= max_per_market:
            rejection_reasons.append(
                "market exposure exceeded"
            )

        if family_counts[family] >= max_per_market_family:
            rejection_reasons.append(
                "market family exposure exceeded"
            )

        if rejection_reasons:
            rejected.append({
                **pick,
                "exposure_rejected": True,
                "exposure_reasons": rejection_reasons,
            })
            continue

        accepted.append({
            **pick,
            "market_family": family,
            "exposure_rejected": False,
        })

        league_counts[league] += 1
        market_counts[market] += 1
        family_counts[family] += 1

    return {
        "accepted_picks": accepted,
        "rejected_picks": rejected,
        "exposure_summary": {
            "league_counts": dict(league_counts),
            "market_counts": dict(market_counts),
            "family_counts": dict(family_counts),
        },
    }