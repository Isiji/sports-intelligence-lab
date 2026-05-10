from sqlalchemy import text
from sqlalchemy.orm import Session

from app.odds.canonical_markets import supported_market_keys


def calculate_market_quality(session: Session) -> dict:
    rows = session.execute(
        text(
            """
            SELECT
                canonical_market,
                SUM(usage_count) AS odds_rows,
                COUNT(*) AS synonym_pairs
            FROM odds_market_synonyms
            WHERE active = TRUE
            GROUP BY canonical_market
            """
        )
    ).mappings().all()

    by_market = {
        row["canonical_market"]: {
            "odds_rows": int(row["odds_rows"] or 0),
            "synonym_pairs": int(row["synonym_pairs"] or 0),
        }
        for row in rows
    }

    report = {}

    for market in supported_market_keys():
        odds_rows = by_market.get(market, {}).get("odds_rows", 0)
        synonym_pairs = by_market.get(market, {}).get("synonym_pairs", 0)

        if odds_rows >= 25000:
            tier = "ELITE"
            enabled = True
        elif odds_rows >= 10000:
            tier = "STRONG"
            enabled = True
        elif odds_rows >= 3000:
            tier = "EXPERIMENTAL"
            enabled = True
        else:
            tier = "DISABLED"
            enabled = False

        report[market] = {
            "market": market,
            "odds_rows": odds_rows,
            "synonym_pairs": synonym_pairs,
            "tier": tier,
            "enabled": enabled,
        }

    return {
        "status": "ok",
        "markets": report,
    }


def get_enabled_markets(session: Session) -> list[str]:
    quality = calculate_market_quality(session)
    return [
        market
        for market, data in quality["markets"].items()
        if data["enabled"]
    ]