# backend/app/services/match_flag_rebuild_service.py

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def rebuild_match_flags(session: Session) -> dict:
    stats_true = session.execute(
        text(
            """
            UPDATE matches m
            SET has_stats = true
            WHERE EXISTS (
                SELECT 1
                FROM team_match_stats tms
                WHERE tms.match_id = m.id
                  AND tms.is_real = true
            )
            """
        )
    ).rowcount

    stats_false = session.execute(
        text(
            """
            UPDATE matches m
            SET has_stats = false
            WHERE NOT EXISTS (
                SELECT 1
                FROM team_match_stats tms
                WHERE tms.match_id = m.id
                  AND tms.is_real = true
            )
            """
        )
    ).rowcount

    odds_true = session.execute(
        text(
            """
            UPDATE matches m
            SET has_odds = true
            WHERE EXISTS (
                SELECT 1
                FROM match_odds mo
                WHERE mo.match_id = m.id
            )
            """
        )
    ).rowcount

    odds_false = session.execute(
        text(
            """
            UPDATE matches m
            SET has_odds = false
            WHERE NOT EXISTS (
                SELECT 1
                FROM match_odds mo
                WHERE mo.match_id = m.id
            )
            """
        )
    ).rowcount

    placeholder_stats = session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM matches m
            WHERE m.has_stats = false
              AND EXISTS (
                  SELECT 1
                  FROM team_match_stats tms
                  WHERE tms.match_id = m.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM team_match_stats tms
                  WHERE tms.match_id = m.id
                    AND tms.is_real = true
              )
            """
        )
    ).scalar()

    summary = session.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_matches,
                COUNT(*) FILTER (WHERE has_stats = true) AS matches_with_stats,
                COUNT(*) FILTER (WHERE has_odds = true) AS matches_with_odds,
                COUNT(*) FILTER (WHERE has_stats = false) AS matches_missing_stats,
                COUNT(*) FILTER (WHERE has_odds = false) AS matches_missing_odds
            FROM matches
            """
        )
    ).mappings().first()

    session.commit()

    return {
        "status": "ok",
        "stats_marked_true": stats_true,
        "stats_marked_false": stats_false,
        "odds_marked_true": odds_true,
        "odds_marked_false": odds_false,
        "placeholder_stats_rows_exist_but_not_real": int(placeholder_stats or 0),
        "summary": dict(summary or {}),
    }