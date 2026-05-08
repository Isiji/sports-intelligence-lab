# backend/app/analysis/market_survivability_report.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def market_survivability_report(
    session: Session,
    run_tag: str,
    min_bets: int = 20,
):
    query = text(
        """
        SELECT
            market,

            COUNT(*) AS bets,

            SUM(
                CASE
                    WHEN won = true THEN 1
                    ELSE 0
                END
            ) AS wins,

            SUM(
                CASE
                    WHEN won = false THEN 1
                    ELSE 0
                END
            ) AS losses,

            ROUND(
                (
                    SUM(
                        CASE
                            WHEN won = true THEN 1
                            ELSE 0
                        END
                    )::numeric
                    / NULLIF(COUNT(*), 0)::numeric
                ),
                4
            ) AS hit_rate,

            ROUND(AVG(odds)::numeric, 3) AS avg_odds,

            ROUND(AVG(confidence)::numeric, 4) AS avg_confidence,

            ROUND(
                AVG(value_score)::numeric,
                4
            ) AS avg_value_score,

            ROUND(
                SUM(profit)::numeric,
                2
            ) AS total_profit,

            ROUND(
                (
                    SUM(profit)::numeric
                    / NULLIF(SUM(stake), 0)::numeric
                ),
                4
            ) AS roi

        FROM historical_backtest_bets

        WHERE run_tag = :run_tag
        AND odds IS NOT NULL

        GROUP BY market

        ORDER BY
            roi DESC,
            hit_rate DESC,
            bets DESC
        """
    )
    rows = session.execute(query, {"run_tag": run_tag}).mappings().all()

    print("\n=== MARKET SURVIVABILITY REPORT ===")
    print(f"Run tag: {run_tag}")
    print(f"Min bets for trust: {min_bets}\n")

    if not rows:
        print("No cached historical bets found.")
        return []

    results = []

    for row in rows:
        bets = int(row["bets"])
        hit_rate = float(row["hit_rate"] or 0)
        roi = float(row["roi"] or 0)
        avg_conf = float(row["avg_confidence"] or 0)
        avg_value = float(row["avg_value_score"] or 0)

        survivability_score = round(
            (hit_rate * 40)
            + (max(roi, -1) * 30)
            + (avg_conf * 20)
            + (avg_value * 10),
            4,
        )

        if bets < min_bets:
            verdict = "NEEDS_MORE_DATA"
        elif roi > 0 and hit_rate >= 0.55:
            verdict = "ACCUMULATOR_SAFE"
        elif roi > 0:
            verdict = "VALUE_ONLY"
        elif hit_rate >= 0.60 and roi <= 0:
            verdict = "LOW_ODDS_TRAP"
        else:
            verdict = "RISKY"

        item = {
            "market": row["market"],
            "bets": bets,
            "wins": int(row["wins"] or 0),
            "losses": int(row["losses"] or 0),
            "hit_rate": hit_rate,
            "avg_odds": float(row["avg_odds"] or 0),
            "avg_confidence": avg_conf,
            "avg_value_score": avg_value,
            "total_profit": float(row["total_profit"] or 0),
            "roi": roi,
            "survivability_score": survivability_score,
            "verdict": verdict,
        }

        results.append(item)
        print(item)

    return results