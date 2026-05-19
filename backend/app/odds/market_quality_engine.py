# backend/app/odds/market_quality_engine.py

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.odds.canonical_markets import CANONICAL_MARKETS


CORE_PRODUCTION_MARKETS = [
    "home_win",
    "away_win",
    "draw",

    "double_chance_1x",
    "double_chance_x2",
    "double_chance_12",

    "over_1_5_goals",
    "under_1_5_goals",
    "over_2_5_goals",
    "under_2_5_goals",
    "over_3_5_goals",
    "under_3_5_goals",

    "btts_yes",
    "btts_no",
]


EXECUTABLE_DISCOVERY_MARKETS = [
    "asian_handicap_home_minus_0_5",
    "asian_handicap_away_minus_0_5",
    "asian_handicap_home_plus_0_5",
    "asian_handicap_away_plus_0_5",

    "asian_handicap_home_minus_1_5",
    "asian_handicap_away_minus_1_5",
    "asian_handicap_home_plus_1_5",
    "asian_handicap_away_plus_1_5",

    "draw_no_bet_home",
    "draw_no_bet_away",

    "corners_over_8_5",
    "corners_under_8_5",
    "corners_over_9_5",
    "corners_under_9_5",

    "shots_on_target_over_8_5",
    "shots_on_target_under_8_5",
]


BOOKMAKER_RICH_MARKET_FAMILIES = {
    "goals_total",
    "team_goals_total",
    "corners_total",
    "shots_on_target_total",
    "first_half_goals_total",
    "first_half_result",
    "asian_handicap",
    "draw_no_bet",
}


MIN_ODDS_ROWS_FOR_DYNAMIC_ENABLE = 50
MIN_MATCHES_WITH_ODDS_FOR_DYNAMIC_ENABLE = 15
MIN_BOOKMAKERS_FOR_RICH_MARKET = 3


def _market_family(market: str) -> str:
    canonical = CANONICAL_MARKETS.get(market)
    return canonical.family if canonical else "unknown"


def calculate_market_quality(session: Session) -> dict:
    rows = session.execute(
        text(
            """
            SELECT
                market,
                COUNT(*) AS odds_rows,
                COUNT(DISTINCT match_id) AS matches_with_odds,
                COUNT(DISTINCT bookmaker) AS bookmaker_count
            FROM match_odds
            WHERE market IS NOT NULL
            GROUP BY market
            ORDER BY COUNT(*) DESC
            """
        )
    ).mappings().all()

    markets: dict[str, dict] = {}

    for market in CORE_PRODUCTION_MARKETS:
        markets[market] = {
            "market": market,
            "family": _market_family(market),
            "odds_rows": 0,
            "matches_with_odds": 0,
            "bookmaker_count": 0,
            "enabled": True,
            "quality_tier": "core_production",
            "reason": "core_market_enabled_by_default",
        }

    for market in EXECUTABLE_DISCOVERY_MARKETS:
        if market not in CANONICAL_MARKETS:
            continue

        markets[market] = {
            "market": market,
            "family": _market_family(market),
            "odds_rows": 0,
            "matches_with_odds": 0,
            "bookmaker_count": 0,
            "enabled": True,
            "quality_tier": "executable_discovery_production",
            "reason": "exact_executable_market_enabled_for_adaptive_growth",
        }

    for row in rows:
        market = str(row["market"])
        odds_rows = int(row["odds_rows"] or 0)
        matches_with_odds = int(row["matches_with_odds"] or 0)
        bookmaker_count = int(row["bookmaker_count"] or 0)

        canonical = CANONICAL_MARKETS.get(market)
        family = canonical.family if canonical else "unknown"

        is_core = market in CORE_PRODUCTION_MARKETS
        is_executable_discovery = market in EXECUTABLE_DISCOVERY_MARKETS
        is_bookmaker_rich_family = family in BOOKMAKER_RICH_MARKET_FAMILIES

        dynamically_enabled = (
            is_bookmaker_rich_family
            and odds_rows >= MIN_ODDS_ROWS_FOR_DYNAMIC_ENABLE
            and matches_with_odds >= MIN_MATCHES_WITH_ODDS_FOR_DYNAMIC_ENABLE
            and bookmaker_count >= MIN_BOOKMAKERS_FOR_RICH_MARKET
        )

        enabled = is_core or is_executable_discovery or dynamically_enabled

        if is_core:
            quality_tier = "core_production"
            reason = "core_market_enabled_by_default"

        elif is_executable_discovery:
            quality_tier = "executable_discovery_production"
            reason = "exact_executable_market_enabled_for_adaptive_growth"

        elif dynamically_enabled:
            quality_tier = "bookmaker_rich_dynamic_production"
            reason = "bookmaker_rich_market_has_enough_odds_depth"

        elif is_bookmaker_rich_family:
            quality_tier = "bookmaker_rich_discovery"
            reason = "bookmaker_rich_market_detected_but_not_mature_enough"

        else:
            quality_tier = "discovery_only"
            reason = "market_not_yet_supported_for_prediction_production"

        markets[market] = {
            "market": market,
            "family": family,
            "odds_rows": odds_rows,
            "matches_with_odds": matches_with_odds,
            "bookmaker_count": bookmaker_count,
            "enabled": enabled,
            "quality_tier": quality_tier,
            "reason": reason,
        }

    return {
        "markets": markets,
        "core_production_markets": CORE_PRODUCTION_MARKETS,
        "executable_discovery_markets": EXECUTABLE_DISCOVERY_MARKETS,
        "bookmaker_rich_market_families": sorted(BOOKMAKER_RICH_MARKET_FAMILIES),
        "dynamic_thresholds": {
            "min_odds_rows": MIN_ODDS_ROWS_FOR_DYNAMIC_ENABLE,
            "min_matches_with_odds": MIN_MATCHES_WITH_ODDS_FOR_DYNAMIC_ENABLE,
            "min_bookmakers": MIN_BOOKMAKERS_FOR_RICH_MARKET,
        },
    }


def get_enabled_markets(session: Session) -> list[str]:
    quality = calculate_market_quality(session)

    enabled = [
        market
        for market, data in quality["markets"].items()
        if data.get("enabled") is True
    ]

    return sorted(set(enabled))