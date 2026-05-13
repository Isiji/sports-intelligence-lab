# backend/app/services/league_decay_service.py

from sqlalchemy import text
from sqlalchemy.orm import Session


class LeagueDecayService:
    """
    Detects stale leagues and reduces priority naturally.

    No permanent exclusion.
    No permanent whitelist.
    Weak leagues cool down.
    Strong leagues can recover later.
    """

    def mark_stale_leagues(self, session: Session, stale_after_days: int = 14) -> dict:
        result = session.execute(
            text(
                """
                UPDATE league_odds_coverage_snapshots
                SET
                    priority_tier = CASE
                        WHEN priority_tier = 'CORE_PRODUCTION' THEN 'HIGH_PRIORITY'
                        WHEN priority_tier = 'HIGH_PRIORITY' THEN 'GROWTH_PRIORITY'
                        WHEN priority_tier = 'GROWTH_PRIORITY' THEN 'EXPLORATION_PRIORITY'
                        WHEN priority_tier = 'EXPLORATION_PRIORITY' THEN 'DISCOVERY_ROTATION'
                        ELSE priority_tier
                    END,
                    updated_at = NOW()
                WHERE updated_at < NOW() - (:stale_after_days || ' days')::interval
                RETURNING league
                """
            ),
            {"stale_after_days": stale_after_days},
        )

        leagues = [row[0] for row in result.fetchall()]
        session.commit()

        return {
            "stale_leagues_marked": len(leagues),
            "leagues": leagues[:50],
        }