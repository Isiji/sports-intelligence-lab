# backend/app/reports/competition_coverage.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def build_competition_coverage_report(session: Session, limit: int = 100) -> dict:
    summary_query = text(
        """
        SELECT
            COUNT(DISTINCT c.id) AS competitions,
            COUNT(DISTINCT co.id) AS countries,
            COUNT(m.id) AS total_matches,
            COUNT(CASE WHEN m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL THEN 1 END) AS finished_matches,
            COUNT(CASE WHEN m.home_goals IS NULL AND m.away_goals IS NULL THEN 1 END) AS upcoming_matches,
            COUNT(CASE WHEN m.has_stats = true THEN 1 END) AS matches_with_real_stats,
            COUNT(CASE WHEN m.has_odds = true THEN 1 END) AS matches_with_odds
        FROM matches m
        LEFT JOIN competitions c ON c.id = m.competition_id
        LEFT JOIN countries co ON co.id = c.country_id
        """
    )

    rows_query = text(
        """
        SELECT
            COALESCE(co.name, 'Unknown') AS country,
            COALESCE(c.name, m.league) AS competition,
            COALESCE(c.competition_type, 'unknown') AS competition_type,
            COUNT(m.id) AS total_matches,
            COUNT(CASE WHEN m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL THEN 1 END) AS finished_matches,
            COUNT(CASE WHEN m.home_goals IS NULL AND m.away_goals IS NULL THEN 1 END) AS upcoming_matches,
            COUNT(CASE WHEN m.has_stats = true THEN 1 END) AS matches_with_real_stats,
            COUNT(CASE WHEN m.has_odds = true THEN 1 END) AS matches_with_odds,
            MIN(m.kickoff_date) AS first_match_date,
            MAX(m.kickoff_date) AS last_match_date
        FROM matches m
        LEFT JOIN competitions c ON c.id = m.competition_id
        LEFT JOIN countries co ON co.id = c.country_id
        GROUP BY
            COALESCE(co.name, 'Unknown'),
            COALESCE(c.name, m.league),
            COALESCE(c.competition_type, 'unknown')
        ORDER BY total_matches DESC
        LIMIT :limit
        """
    )

    summary = session.execute(summary_query).mappings().first()
    rows = session.execute(rows_query, {"limit": limit}).mappings().all()

    return {
        "summary": dict(summary or {}),
        "competitions": [dict(row) for row in rows],
    }