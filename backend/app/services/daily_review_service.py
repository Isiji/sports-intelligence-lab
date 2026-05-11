from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session


def daily_prediction_review(
    session: Session,
    review_date: date | None = None,
) -> dict:
    selected_date = (
        review_date
        or (date.today() - timedelta(days=1))
    )

    rows = session.execute(
        text(
            """
            SELECT
                po.league,
                po.market,

                COUNT(*) AS bets,

                SUM(
                    CASE
                        WHEN po.won = true
                        THEN 1
                        ELSE 0
                    END
                ) AS wins,

                ROUND(
                    AVG(
                        CASE
                            WHEN po.won = true
                            THEN 1.0
                            ELSE 0.0
                        END
                    )::numeric,
                    4
                ) AS hit_rate,

                ROUND(
                    AVG(po.profit)::numeric,
                    4
                ) AS roi,

                ROUND(
                    AVG(po.confidence)::numeric,
                    4
                ) AS avg_confidence,

                ROUND(
                    AVG(po.value_score)::numeric,
                    4
                ) AS avg_value_score

            FROM prediction_outcomes po

            WHERE DATE(po.settled_at)
                  = :selected_date

            GROUP BY
                po.league,
                po.market

            ORDER BY
                roi DESC,
                hit_rate DESC,
                bets DESC
            """
        ),
        {
            "selected_date": selected_date,
        },
    ).mappings().all()

    total_bets = 0
    total_profit = 0.0
    total_wins = 0

    summaries = []

    for row in rows:
        bets = int(row["bets"] or 0)
        wins = int(row["wins"] or 0)
        roi = float(row["roi"] or 0.0)

        total_bets += bets
        total_profit += roi * bets
        total_wins += wins

        verdict = _resolve_verdict(
            roi=roi,
            hit_rate=float(row["hit_rate"] or 0.0),
        )

        summaries.append(
            {
                "league": row["league"],
                "market": row["market"],
                "bets": bets,
                "wins": wins,
                "hit_rate": float(
                    row["hit_rate"] or 0.0
                ),
                "roi": roi,
                "avg_confidence": float(
                    row["avg_confidence"] or 0.0
                ),
                "avg_value_score": float(
                    row["avg_value_score"] or 0.0
                ),
                "verdict": verdict,
            }
        )

    overall_hit_rate = (
        total_wins / total_bets
        if total_bets
        else 0.0
    )

    overall_roi = (
        total_profit / total_bets
        if total_bets
        else 0.0
    )

    return {
        "date": str(selected_date),
        "total_bets": total_bets,
        "overall_hit_rate": round(
            overall_hit_rate,
            4,
        ),
        "overall_roi": round(
            overall_roi,
            4,
        ),
        "league_market_reviews": summaries,
    }


def _resolve_verdict(
    roi: float,
    hit_rate: float,
) -> str:
    if roi >= 0.20 and hit_rate >= 0.65:
        return "ELITE"

    if roi >= 0.10 and hit_rate >= 0.58:
        return "STRONG"

    if roi >= 0:
        return "STABLE"

    if roi >= -0.10:
        return "VOLATILE"

    return "DANGEROUS"