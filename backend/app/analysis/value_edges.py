# backend/app/analysis/value_edges.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_value_edges(
    session: Session,
    slate: str = "demo",
    min_edge: float = 0.05,
    limit: int = 50,
):
    query = text(
        """
        SELECT
            p.id,
            p.slate,
            p.match_id,
            m.league,
            m.home_team,
            m.away_team,
            p.market,
            p.predicted_label,
            p.confidence,
            p.odds,
            p.implied_probability,
            p.value_score,
            p.model_name,
            m.kickoff_date

        FROM predictions p
        JOIN matches m
            ON m.id = p.match_id

        WHERE p.slate = :slate
          AND p.odds IS NOT NULL
          AND p.implied_probability IS NOT NULL
          AND p.value_score IS NOT NULL
          AND p.value_score >= :min_edge

        ORDER BY
            p.value_score DESC,
            p.confidence DESC,
            p.odds DESC

        LIMIT :limit
        """
    )

    rows = session.execute(
        query,
        {
            "slate": slate,
            "min_edge": min_edge,
            "limit": limit,
        },
    ).mappings().all()

    return [dict(row) for row in rows]