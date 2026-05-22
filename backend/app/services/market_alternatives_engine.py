# backend/app/services/market_alternatives_engine.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketAlternative:
    market: str
    priority: int
    reason: str


ALTERNATIVE_MAP = {
    "asian_handicap_home_plus_1_5": [
        MarketAlternative(
            market="double_chance_1x",
            priority=1,
            reason="safer handicap fallback",
        ),
        MarketAlternative(
            market="draw_no_bet_home",
            priority=2,
            reason="reduced line volatility",
        ),
        MarketAlternative(
            market="over_1_5_goals",
            priority=3,
            reason="execution survivability",
        ),
    ],
    "asian_handicap_away_plus_1_5": [
        MarketAlternative(
            market="double_chance_x2",
            priority=1,
            reason="safer handicap fallback",
        ),
        MarketAlternative(
            market="draw_no_bet_away",
            priority=2,
            reason="reduced line volatility",
        ),
        MarketAlternative(
            market="over_1_5_goals",
            priority=3,
            reason="execution survivability",
        ),
    ],
    "corners_over_8_5": [
        MarketAlternative(
            market="over_1_5_goals",
            priority=1,
            reason="corners volatility fallback",
        ),
        MarketAlternative(
            market="btts_yes",
            priority=2,
            reason="market persistence",
        ),
    ],
    "shots_on_target_over_8_5": [
        MarketAlternative(
            market="over_1_5_goals",
            priority=1,
            reason="shots market fallback",
        ),
        MarketAlternative(
            market="btts_yes",
            priority=2,
            reason="market persistence",
        ),
    ],
}


def resolve_market_alternatives(
    market: str,
) -> list[dict]:

    alternatives = ALTERNATIVE_MAP.get(
        str(market),
        [],
    )

    return [
        {
            "market": item.market,
            "priority": item.priority,
            "reason": item.reason,
        }
        for item in sorted(
            alternatives,
            key=lambda x: x.priority,
        )
    ]