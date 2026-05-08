# backend/app/analysis/confidence_band_survivability_report.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def confidence_band_survivability_report(
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
                    WHEN confidence < 0.60 THEN '0.00 - 0.59'
                    WHEN confidence >= 0.60 AND confidence < 0.70 THEN '0.60 - 0.69'
                    WHEN confidence >= 0.70 AND confidence < 0.80 THEN '0.70 - 0.79'
                    WHEN confidence >= 0.80 AND confidence < 0.90 THEN '0.80 - 0.89'
                    ELSE '0.90+'
                END AS confidence_band,
                won,
                odds,
                confidence,
                value_score,
                profit,
                stake
            FROM historical_backtest_bets
            WHERE run_tag = :run_tag
              AND odds IS NOT NULL
              AND confidence IS NOT NULL
        )

        SELECT
            market,
            confidence_band,
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

        GROUP BY market, confidence_band

        ORDER BY
            market ASC,
            roi DESC,
            hit_rate DESC,
            bets DESC
        """
    )

    rows = session.execute(query, {"run_tag": run_tag}).mappings().all()

    print("\n=== CONFIDENCE BAND SURVIVABILITY REPORT ===")
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
        avg_odds = float(row["avg_odds"] or 0)
        avg_value_score = float(row["avg_value_score"] or 0)

        survivability_score = round(
            (hit_rate * 40)
            + (max(roi, -1) * 35)
            + (avg_value_score * 15)
            + ((1 / avg_odds) * 10 if avg_odds > 0 else 0),
            4,
        )

        if bets < min_bets:
            verdict = "NEEDS_MORE_DATA"
        elif roi > 0 and hit_rate >= 0.55:
            verdict = "TRUSTED_CONFIDENCE_ZONE"
        elif roi > 0:
            verdict = "VALUE_CONFIDENCE_ZONE"
        elif hit_rate >= 0.60 and roi <= 0:
            verdict = "CONFIDENCE_TRAP"
        else:
            verdict = "UNTRUSTED_CONFIDENCE_ZONE"

        item = {
            "market": row["market"],
            "confidence_band": row["confidence_band"],
            "bets": bets,
            "wins": int(row["wins"] or 0),
            "losses": int(row["losses"] or 0),
            "hit_rate": hit_rate,
            "avg_odds": avg_odds,
            "avg_confidence": float(row["avg_confidence"] or 0),
            "avg_value_score": avg_value_score,
            "total_profit": float(row["total_profit"] or 0),
            "roi": roi,
            "survivability_score": survivability_score,
            "verdict": verdict,
        }

        results.append(item)
        print(item)

    return results