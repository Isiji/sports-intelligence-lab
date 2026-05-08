# backend/app/backtest/market_profitability.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_market_profitability(session: Session, slate: str | None = None):
    slate_filter = "AND p.slate = :slate" if slate else ""

    query = text(f"""
        SELECT
            p.market,
            m.league,

            COUNT(*) AS total_bets,

            SUM(
                CASE
                    WHEN p.predicted_label = m.winner THEN 1
                    ELSE 0
                END
            ) AS wins,

            ROUND(
                AVG(
                    CASE
                        WHEN p.predicted_label = m.winner THEN 1.0
                        ELSE 0.0
                    END
                )::numeric,
                4
            ) AS hit_rate,

            ROUND(AVG(p.odds)::numeric, 4) AS avg_odds,
            ROUND(AVG(p.confidence)::numeric, 4) AS avg_confidence,
            ROUND(AVG(p.value_score)::numeric, 4) AS avg_edge,

            ROUND(
                SUM(
                    CASE
                        WHEN p.predicted_label = m.winner
                        THEN p.odds - 1
                        ELSE -1
                    END
                )::numeric,
                4
            ) AS profit_units,

            ROUND(
                (
                    SUM(
                        CASE
                            WHEN p.predicted_label = m.winner
                            THEN p.odds - 1
                            ELSE -1
                        END
                    ) / COUNT(*)
                )::numeric,
                4
            ) AS roi

        FROM predictions p
        JOIN matches m
            ON m.id = p.match_id

        
        WHERE p.odds IS NOT NULL
          AND p.implied_probability IS NOT NULL
          AND p.value_score IS NOT NULL
          {slate_filter}

        GROUP BY p.market, m.league

        HAVING COUNT(*) >= 5

        ORDER BY roi DESC, profit_units DESC;
    """)

    params = {}
    if slate:
        params["slate"] = slate

    rows = session.execute(query, params).mappings().all()
    return [dict(row) for row in rows]


def summarize_market_profitability(session: Session, slate: str | None = None):
    rows = get_market_profitability(session=session, slate=slate)

    if not rows:
        return {
            "best_markets": [],
            "worst_markets": [],
            "best_leagues": [],
            "worst_leagues": [],
            "all": [],
        }

    by_market = {}

    for row in rows:
        market = row["market"]

        if market not in by_market:
            by_market[market] = {
                "market": market,
                "total_bets": 0,
                "wins": 0,
                "profit_units": 0.0,
                "weighted_roi_sum": 0.0,
            }

        by_market[market]["total_bets"] += row["total_bets"]
        by_market[market]["wins"] += row["wins"]
        by_market[market]["profit_units"] += float(row["profit_units"])
        by_market[market]["weighted_roi_sum"] += float(row["roi"]) * row["total_bets"]

    market_summary = []

    for item in by_market.values():
        total = item["total_bets"]
        wins = item["wins"]

        market_summary.append({
            "market": item["market"],
            "total_bets": total,
            "wins": wins,
            "hit_rate": round(wins / total, 4) if total else 0,
            "profit_units": round(item["profit_units"], 4),
            "roi": round(item["profit_units"] / total, 4) if total else 0,
        })

    market_summary.sort(key=lambda x: x["roi"], reverse=True)

    league_summary = rows[:]
    league_summary.sort(key=lambda x: x["roi"], reverse=True)

    return {
        "best_markets": market_summary[:5],
        "worst_markets": market_summary[-5:],
        "best_leagues": league_summary[:10],
        "worst_leagues": league_summary[-10:],
        "all": rows,
    }