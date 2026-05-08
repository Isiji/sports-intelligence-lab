# backend/app/analysis/odds_band_survivability_report.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def odds_band_survivability_report(
    session: Session,
    run_tag: str,
    min_bets: int = 10,
):
    query = text(
        """
        WITH banded AS (
            SELECT
                market,
                CASE
                    WHEN odds < 1.30 THEN '1.00 - 1.29'
                    WHEN odds >= 1.30 AND odds < 1.50 THEN '1.30 - 1.49'
                    WHEN odds >= 1.50 AND odds < 1.80 THEN '1.50 - 1.79'
                    WHEN odds >= 1.80 AND odds < 2.20 THEN '1.80 - 2.19'
                    WHEN odds >= 2.20 AND odds < 3.00 THEN '2.20 - 2.99'
                    WHEN odds >= 3.00 AND odds < 4.50 THEN '3.00 - 4.49'
                    ELSE '4.50+'
                END AS odds_band,
                won,
                odds,
                confidence,
                value_score,
                profit,
                stake
            FROM historical_backtest_bets
            WHERE run_tag = :run_tag
              AND odds IS NOT NULL
        )

        SELECT
            market,
            odds_band,
            COUNT(*) AS bets,

            SUM(CASE WHEN won = true THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN won = false THEN 1 ELSE 0 END) AS losses,

            ROUND(
                (
                    SUM(CASE WHEN won = true THEN 1 ELSE 0 END)::numeric
                    / NULLIF(COUNT(*), 0)::numeric
                ),
                4
            ) AS hit_rate,

            ROUND(AVG(odds)::numeric, 3) AS avg_odds,
            ROUND(AVG(confidence)::numeric, 4) AS avg_confidence,
            ROUND(AVG(value_score)::numeric, 4) AS avg_value_score,
            ROUND(SUM(profit)::numeric, 2) AS total_profit,

            ROUND(
                (
                    SUM(profit)::numeric
                    / NULLIF(SUM(stake), 0)::numeric
                ),
                4
            ) AS roi

        FROM banded

        GROUP BY market, odds_band

        ORDER BY
            market ASC,
            roi DESC,
            hit_rate DESC,
            bets DESC
        """
    )

    rows = session.execute(query, {"run_tag": run_tag}).mappings().all()

    print("\n=== ODDS BAND SURVIVABILITY REPORT ===")
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
        avg_confidence = float(row["avg_confidence"] or 0)
        avg_value_score = float(row["avg_value_score"] or 0)

        survivability_score = round(
            (hit_rate * 40)
            + (max(roi, -1) * 35)
            + (avg_confidence * 15)
            + (avg_value_score * 10),
            4,
        )

        if bets < min_bets:
            verdict = "NEEDS_MORE_DATA"
        elif roi > 0 and hit_rate >= 0.55:
            verdict = "ACCUMULATOR_SAFE_ZONE"
        elif roi > 0:
            verdict = "VALUE_ZONE"
        elif hit_rate >= 0.60 and roi <= 0:
            verdict = "LOW_ODDS_TRAP_ZONE"
        else:
            verdict = "AVOID_ZONE"

        item = {
            "market": row["market"],
            "odds_band": row["odds_band"],
            "bets": bets,
            "wins": int(row["wins"] or 0),
            "losses": int(row["losses"] or 0),
            "hit_rate": hit_rate,
            "avg_odds": float(row["avg_odds"] or 0),
            "avg_confidence": avg_confidence,
            "avg_value_score": avg_value_score,
            "total_profit": float(row["total_profit"] or 0),
            "roi": roi,
            "survivability_score": survivability_score,
            "verdict": verdict,
        }

        results.append(item)
        print(item)

    return results