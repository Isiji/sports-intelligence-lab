from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.intelligence.portfolio_filters import evaluate_pick_for_portfolio
from app.utils.slate import resolve_slate


def build_prediction_review_report(
    *,
    session: Session,
    slate: str | None = None,
    limit: int = 80,
    require_odds: bool = False,
) -> dict:
    selected_slate = resolve_slate(slate)

    odds_filter = "AND p.odds IS NOT NULL" if require_odds else ""

    query = text(
        f"""
        SELECT
            p.id AS prediction_id,
            p.slate,
            p.match_id,
            m.league,
            m.home_team,
            m.away_team,
            m.kickoff_date,
            p.market,
            p.predicted_label,
            p.confidence,
            p.odds,
            p.implied_probability,
            p.value_score,
            p.model_name
        FROM predictions p
        JOIN matches m
            ON m.id = p.match_id
        WHERE p.slate = :slate
          {odds_filter}
        ORDER BY
            p.confidence DESC,
            p.value_score DESC NULLS LAST,
            p.odds ASC NULLS LAST
        LIMIT :limit
        """
    )

    rows = session.execute(
        query,
        {
            "slate": selected_slate,
            "limit": limit,
        },
    ).mappings().all()

    reviewed = []

    for row in rows:
        item = dict(row)

        portfolio = evaluate_pick_for_portfolio(
            session=session,
            league=item.get("league"),
            market=item["market"],
            confidence=float(item["confidence"] or 0.0),
            odds=float(item["odds"]) if item.get("odds") is not None else None,
            value_score=(
                float(item["value_score"])
                if item.get("value_score") is not None
                else None
            ),
            strict=True,
        )

        item["portfolio_allowed"] = portfolio.allowed
        item["portfolio_tier"] = portfolio.tier
        item["portfolio_risk_score"] = portfolio.risk_score
        item["portfolio_reason"] = portfolio.reason
        item["portfolio_flags"] = portfolio.risk_flags

        reviewed.append(item)

    approved = [
        item for item in reviewed
        if item["portfolio_allowed"]
    ]

    rejected = [
        item for item in reviewed
        if not item["portfolio_allowed"]
    ]

    return {
        "slate": selected_slate,
        "total_predictions_reviewed": len(reviewed),
        "approved_predictions": len(approved),
        "rejected_predictions": len(rejected),
        "require_odds": require_odds,
        "predictions": reviewed,
    }