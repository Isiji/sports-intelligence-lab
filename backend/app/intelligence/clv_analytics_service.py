# backend/app/intelligence/clv_analytics_service.py

from __future__ import annotations

from statistics import mean

from sqlalchemy.orm import Session

from app.db.models import PredictionOutcome


def build_clv_analytics(
    session: Session,
) -> dict:
    rows = (
        session.query(PredictionOutcome)
        .filter(
            PredictionOutcome.clv.isnot(None),
            PredictionOutcome.odds.isnot(None),
            PredictionOutcome.closing_odds.isnot(None),
        )
        .all()
    )

    if not rows:
        return {
            "records": 0,
            "message": "No CLV records found.",
        }

    clv_values = [
        float(row.clv)
        for row in rows
        if row.clv is not None
    ]

    positive_clv = [
        value
        for value in clv_values
        if value > 0
    ]

    avg_opening_odds = round(
        mean(
            float(row.odds)
            for row in rows
            if row.odds is not None
        ),
        4,
    )

    avg_closing_odds = round(
        mean(
            float(row.closing_odds)
            for row in rows
            if row.closing_odds is not None
        ),
        4,
    )

    avg_clv = round(
        mean(clv_values),
        6,
    )

    positive_clv_rate = round(
        len(positive_clv)
        / max(len(clv_values), 1),
        6,
    )

    profitable_positive_clv = sum(
        1
        for row in rows
        if (
            row.clv is not None
            and row.clv > 0
            and row.profit > 0
        )
    )

    total_positive_clv = max(
        len(positive_clv),
        1,
    )

    clv_profitability_correlation = round(
        profitable_positive_clv
        / total_positive_clv,
        6,
    )

    market_groups: dict[str, list[PredictionOutcome]] = {}

    for row in rows:
        market_groups.setdefault(
            row.market,
            [],
        ).append(row)

    market_scores = []

    for market, items in market_groups.items():
        market_avg_clv = round(
            mean(
                float(item.clv or 0.0)
                for item in items
            ),
            6,
        )

        market_scores.append(
            {
                "market": market,
                "bets": len(items),
                "avg_clv": market_avg_clv,
            }
        )

    best_clv_markets = sorted(
        market_scores,
        key=lambda x: x["avg_clv"],
        reverse=True,
    )[:10]

    worst_clv_markets = sorted(
        market_scores,
        key=lambda x: x["avg_clv"],
    )[:10]

    return {
        "records": len(rows),

        "avg_clv": avg_clv,

        "positive_clv_rate": positive_clv_rate,

        "avg_opening_odds": avg_opening_odds,

        "avg_closing_odds": avg_closing_odds,

        "clv_profitability_correlation": (
            clv_profitability_correlation
        ),

        "best_clv_markets": best_clv_markets,

        "worst_clv_markets": worst_clv_markets,
    }