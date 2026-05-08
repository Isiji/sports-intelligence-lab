# backend/app/analysis/league_survivability_report.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def league_survivability_report(
    session: Session,
    run_tag: str,
    min_bets: int = 10,
):
    query = text(
        """
        SELECT
            league,
            COUNT(*) AS bets,

            COUNT(DISTINCT market) AS markets_tested,

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

        FROM historical_backtest_bets

        WHERE run_tag = :run_tag
          AND odds IS NOT NULL
          AND league IS NOT NULL

        GROUP BY league

        ORDER BY
            roi DESC,
            hit_rate DESC,
            bets DESC
        """
    )

    rows = session.execute(query, {"run_tag": run_tag}).mappings().all()

    print("\n=== LEAGUE SURVIVABILITY REPORT ===")
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
            (hit_rate * 35)
            + (max(roi, -1) * 35)
            + (avg_confidence * 15)
            + (avg_value_score * 15),
            4,
        )

        if bets < min_bets:
            verdict = "NEEDS_MORE_DATA"
        elif roi > 0 and hit_rate >= 0.55:
            verdict = "ACCUMULATOR_SAFE_LEAGUE"
        elif roi > 0:
            verdict = "VALUE_LEAGUE"
        elif avg_confidence >= 0.80 and roi <= 0:
            verdict = "FAKE_CONFIDENCE_LEAGUE"
        else:
            verdict = "CHAOS_LEAGUE"

        item = {
            "league": row["league"],
            "bets": bets,
            "markets_tested": int(row["markets_tested"] or 0),
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