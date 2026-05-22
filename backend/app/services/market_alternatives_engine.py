# backend/app/services/market_alternatives_engine.py

from __future__ import annotations

from dataclasses import dataclass

from app.odds.executable_market_registry import (
    parse_executable_market,
)


@dataclass(frozen=True)
class MarketAlternative:
    market: str
    priority: int
    reason: str
    survivability_bias: float


ALTERNATIVE_MAP = {
    "asian_handicap_home_plus_1_5": [
        MarketAlternative(
            market="double_chance_1x",
            priority=1,
            reason="safer handicap fallback",
            survivability_bias=0.92,
        ),
        MarketAlternative(
            market="draw_no_bet_home",
            priority=2,
            reason="reduced line volatility",
            survivability_bias=0.84,
        ),
        MarketAlternative(
            market="home_win",
            priority=3,
            reason="simpler executable line",
            survivability_bias=0.72,
        ),
        MarketAlternative(
            market="over_1_5_goals",
            priority=4,
            reason="execution survivability",
            survivability_bias=0.88,
        ),
    ],

    "asian_handicap_away_plus_1_5": [
        MarketAlternative(
            market="double_chance_x2",
            priority=1,
            reason="safer handicap fallback",
            survivability_bias=0.92,
        ),
        MarketAlternative(
            market="draw_no_bet_away",
            priority=2,
            reason="reduced line volatility",
            survivability_bias=0.84,
        ),
        MarketAlternative(
            market="away_win",
            priority=3,
            reason="simpler executable line",
            survivability_bias=0.72,
        ),
        MarketAlternative(
            market="over_1_5_goals",
            priority=4,
            reason="execution survivability",
            survivability_bias=0.88,
        ),
    ],

    "corners_over_8_5": [
        MarketAlternative(
            market="over_1_5_goals",
            priority=1,
            reason="corners volatility fallback",
            survivability_bias=0.90,
        ),
        MarketAlternative(
            market="btts_yes",
            priority=2,
            reason="market persistence",
            survivability_bias=0.78,
        ),
    ],

    "shots_on_target_over_8_5": [
        MarketAlternative(
            market="over_1_5_goals",
            priority=1,
            reason="shots market fallback",
            survivability_bias=0.90,
        ),
        MarketAlternative(
            market="btts_yes",
            priority=2,
            reason="market persistence",
            survivability_bias=0.78,
        ),
    ],

    "home_win": [
        MarketAlternative(
            market="draw_no_bet_home",
            priority=1,
            reason="lower execution risk",
            survivability_bias=0.91,
        ),
        MarketAlternative(
            market="double_chance_1x",
            priority=2,
            reason="safer result protection",
            survivability_bias=0.95,
        ),
    ],

    "away_win": [
        MarketAlternative(
            market="draw_no_bet_away",
            priority=1,
            reason="lower execution risk",
            survivability_bias=0.91,
        ),
        MarketAlternative(
            market="double_chance_x2",
            priority=2,
            reason="safer result protection",
            survivability_bias=0.95,
        ),
    ],
}


def _dynamic_family_fallbacks(
    market: str,
) -> list[MarketAlternative]:

    executable = parse_executable_market(
        market
    )

    if executable.family == "ASIAN_HANDICAP":

        return [
            MarketAlternative(
                market="double_chance_1x",
                priority=90,
                reason="dynamic handicap fallback",
                survivability_bias=0.92,
            ),
            MarketAlternative(
                market="draw_no_bet_home",
                priority=91,
                reason="dynamic line protection",
                survivability_bias=0.84,
            ),
            MarketAlternative(
                market="over_1_5_goals",
                priority=92,
                reason="market survivability",
                survivability_bias=0.88,
            ),
        ]

    if executable.family in {
        "CORNERS",
        "SHOTS_ON_TARGET",
    }:

        return [
            MarketAlternative(
                market="over_1_5_goals",
                priority=90,
                reason="special market fallback",
                survivability_bias=0.90,
            ),
            MarketAlternative(
                market="btts_yes",
                priority=91,
                reason="persistent market",
                survivability_bias=0.76,
            ),
        ]

    return []


def resolve_market_alternatives(
    market: str,
) -> list[dict]:

    direct = ALTERNATIVE_MAP.get(
        str(market),
        [],
    )

    dynamic = _dynamic_family_fallbacks(
        market
    )

    merged = direct + dynamic

    deduped: dict[str, MarketAlternative] = {}

    for item in merged:

        current = deduped.get(
            item.market
        )

        if (
            current is None
            or item.priority < current.priority
        ):
            deduped[item.market] = item

    return [
        {
            "market": item.market,
            "priority": item.priority,
            "reason": item.reason,
            "survivability_bias": (
                item.survivability_bias
            ),
        }
        for item in sorted(
            deduped.values(),
            key=lambda x: (
                x.priority,
                -x.survivability_bias,
            ),
        )
    ]