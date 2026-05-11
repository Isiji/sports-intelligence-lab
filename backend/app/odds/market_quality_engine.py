from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


PRODUCTION_MARKETS = [
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

    "home_over_0_5_goals",
    "away_over_0_5_goals",

    "home_clean_sheet",
    "away_clean_sheet",

    "corners_over_8_5",
    "shots_on_target_over_8_5",
]


def calculate_market_quality(session: Session) -> dict:
    rows = session.execute(
        text(
            """
            SELECT
                market,
                COUNT(*) AS odds_rows,
                COUNT(DISTINCT match_id) AS matches_with_odds
            FROM match_odds
            GROUP BY market
            ORDER BY COUNT(*) DESC
            """
        )
    ).mappings().all()

    markets: dict[str, dict] = {}

    for market in PRODUCTION_MARKETS:
        markets[market] = {
            "market": market,
            "odds_rows": 0,
            "matches_with_odds": 0,
            "enabled": True,
            "quality_tier": "production_enabled",
        }

    for row in rows:
        market = str(row["market"])

        if market not in markets:
            markets[market] = {
                "market": market,
                "odds_rows": int(row["odds_rows"] or 0),
                "matches_with_odds": int(row["matches_with_odds"] or 0),
                "enabled": True,
                "quality_tier": "production_enabled_from_odds_db",
            }
        else:
            markets[market]["odds_rows"] = int(row["odds_rows"] or 0)
            markets[market]["matches_with_odds"] = int(row["matches_with_odds"] or 0)

    return {
        "markets": markets,
        "production_markets": PRODUCTION_MARKETS,
    }


def get_enabled_markets(session: Session) -> list[str]:
    return PRODUCTION_MARKETS