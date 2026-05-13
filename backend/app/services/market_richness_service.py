# backend/app/services/market_richness_service.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class MarketRichnessService:
    """
    Market richness intelligence.

    Learns:
    - which normalized markets are most available
    - which provider markets are being skipped/unmapped
    - which leagues have rich market depth
    - which market families deserve expansion priority

    No betting advice.
    No hardcoded bookmaker dependency.
    """

    def __init__(
        self,
        session: Session,
        lookback_days: int = 7,
    ):
        self.session = session
        self.lookback_days = lookback_days

    def build_report(self, limit: int = 50) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=self.lookback_days)

        return {
            "lookback_days": self.lookback_days,
            "generated_at": datetime.utcnow().isoformat(),
            "normalized_market_richness": self.normalized_market_richness(
                since=since,
                limit=limit,
            ),
            "league_market_richness": self.league_market_richness(
                since=since,
                limit=limit,
            ),
            "bookmaker_market_richness": self.bookmaker_market_richness(
                since=since,
                limit=limit,
            ),
            "market_expansion_priorities": self.market_expansion_priorities(
                since=since,
                limit=limit,
            ),
        }

    def normalized_market_richness(
        self,
        since: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    market,
                    selection,
                    COUNT(*) AS odds_rows,
                    COUNT(DISTINCT match_id) AS matches_available,
                    COUNT(DISTINCT bookmaker) AS bookmaker_count,
                    ROUND(AVG(odds)::numeric, 4) AS avg_odds,
                    MIN(retrieved_at) AS first_seen_at,
                    MAX(retrieved_at) AS last_seen_at
                FROM match_odds
                WHERE retrieved_at >= :since
                GROUP BY market, selection
                ORDER BY matches_available DESC, odds_rows DESC
                LIMIT :limit
                """
            ),
            {"since": since, "limit": limit},
        ).mappings().all()

        return [dict(row) for row in rows]

    def league_market_richness(
        self,
        since: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    m.league,
                    COUNT(mo.id) AS odds_rows,
                    COUNT(DISTINCT mo.match_id) AS matches_with_odds,
                    COUNT(DISTINCT mo.market) AS normalized_markets,
                    COUNT(DISTINCT mo.bookmaker) AS bookmakers,
                    ROUND(
                        COUNT(DISTINCT mo.market)::numeric
                        / NULLIF(COUNT(DISTINCT mo.match_id), 0),
                        4
                    ) AS markets_per_match
                FROM match_odds mo
                JOIN matches m ON m.id = mo.match_id
                WHERE mo.retrieved_at >= :since
                GROUP BY m.league
                ORDER BY normalized_markets DESC, matches_with_odds DESC
                LIMIT :limit
                """
            ),
            {"since": since, "limit": limit},
        ).mappings().all()

        return [dict(row) for row in rows]

    def bookmaker_market_richness(
        self,
        since: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    COALESCE(bookmaker, 'UNKNOWN') AS bookmaker,
                    COUNT(*) AS odds_rows,
                    COUNT(DISTINCT match_id) AS matches_available,
                    COUNT(DISTINCT market) AS normalized_markets,
                    COUNT(DISTINCT selection) AS selections,
                    ROUND(
                        COUNT(*)::numeric
                        / NULLIF(COUNT(DISTINCT match_id), 0),
                        4
                    ) AS odds_rows_per_match
                FROM match_odds
                WHERE retrieved_at >= :since
                GROUP BY COALESCE(bookmaker, 'UNKNOWN')
                ORDER BY matches_available DESC, normalized_markets DESC, odds_rows DESC
                LIMIT :limit
                """
            ),
            {"since": since, "limit": limit},
        ).mappings().all()

        return [dict(row) for row in rows]

    def market_expansion_priorities(
        self,
        since: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Uses provider_sync_logs as a rough proxy for skipped/unmapped volume.

        The exact unmapped examples are currently returned in command output,
        not persisted. So this report focuses on markets already normalized
        and identifies where normalized coverage is strongest.
        """

        rows = self.session.execute(
            text(
                """
                SELECT
                    market,
                    COUNT(*) AS odds_rows,
                    COUNT(DISTINCT match_id) AS matches_available,
                    COUNT(DISTINCT bookmaker) AS bookmaker_count,
                    CASE
                        WHEN COUNT(DISTINCT match_id) >= 200
                         AND COUNT(DISTINCT bookmaker) >= 5
                        THEN 'CORE_MARKET'

                        WHEN COUNT(DISTINCT match_id) >= 80
                         AND COUNT(DISTINCT bookmaker) >= 3
                        THEN 'EXPAND_CONFIDENTLY'

                        WHEN COUNT(DISTINCT match_id) >= 25
                        THEN 'WATCHLIST'

                        ELSE 'LOW_SAMPLE'
                    END AS expansion_priority
                FROM match_odds
                WHERE retrieved_at >= :since
                GROUP BY market
                ORDER BY matches_available DESC, bookmaker_count DESC
                LIMIT :limit
                """
            ),
            {"since": since, "limit": limit},
        ).mappings().all()

        return [dict(row) for row in rows]