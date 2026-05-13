# backend/app/services/bookmaker_richness_service.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class BookmakerRichnessService:
    """
    Bookmaker richness intelligence.

    Measures bookmaker coverage inside our ingested odds data.

    Tracks:
    - match coverage
    - normalized market depth
    - odds rows per match
    - core market support
    - advanced market support
    - same-bookmaker grouping readiness

    This is technical data coverage analysis only.
    """

    CORE_MARKETS = {
        "home_win",
        "draw",
        "away_win",
        "over_1_5_goals",
        "under_1_5_goals",
        "over_2_5_goals",
        "under_2_5_goals",
        "over_3_5_goals",
        "under_3_5_goals",
        "btts_yes",
        "btts_no",
        "double_chance_1x",
        "double_chance_x2",
        "double_chance_12",
    }

    ADVANCED_PREFIXES = (
        "exact_score_",
        "ht_ft_",
        "first_half_",
        "second_half_",
        "asian_handicap_",
    )

    def __init__(
        self,
        session: Session,
        lookback_days: int = 7,
    ):
        self.session = session
        self.lookback_days = lookback_days

    def build_report(self, limit: int = 30) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=self.lookback_days)

        return {
            "lookback_days": self.lookback_days,
            "generated_at": datetime.utcnow().isoformat(),
            "bookmaker_summary": self.bookmaker_summary(since=since, limit=limit),
            "core_market_support": self.core_market_support(since=since, limit=limit),
            "advanced_market_support": self.advanced_market_support(since=since, limit=limit),
            "same_bookmaker_grouping_readiness": self.same_bookmaker_grouping_readiness(
                since=since,
                limit=limit,
            ),
        }

    def bookmaker_summary(
        self,
        since: datetime,
        limit: int = 30,
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
                    ) AS odds_rows_per_match,
                    MIN(retrieved_at) AS first_seen_at,
                    MAX(retrieved_at) AS last_seen_at
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

    def core_market_support(
        self,
        since: datetime,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    COALESCE(bookmaker, 'UNKNOWN') AS bookmaker,
                    COUNT(DISTINCT market) AS supported_core_markets,
                    COUNT(DISTINCT match_id) AS matches_available,
                    COUNT(*) AS odds_rows
                FROM match_odds
                WHERE retrieved_at >= :since
                  AND market = ANY(:core_markets)
                GROUP BY COALESCE(bookmaker, 'UNKNOWN')
                ORDER BY supported_core_markets DESC, matches_available DESC
                LIMIT :limit
                """
            ),
            {
                "since": since,
                "limit": limit,
                "core_markets": list(self.CORE_MARKETS),
            },
        ).mappings().all()

        output = []

        for row in rows:
            supported = int(row["supported_core_markets"] or 0)
            output.append(
                {
                    "bookmaker": row["bookmaker"],
                    "supported_core_markets": supported,
                    "total_core_markets": len(self.CORE_MARKETS),
                    "core_support_rate": round(supported / len(self.CORE_MARKETS), 4),
                    "matches_available": int(row["matches_available"] or 0),
                    "odds_rows": int(row["odds_rows"] or 0),
                }
            )

        return output

    def advanced_market_support(
        self,
        since: datetime,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    COALESCE(bookmaker, 'UNKNOWN') AS bookmaker,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market LIKE 'exact_score_%'
                    ) AS exact_score_markets,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market LIKE 'ht_ft_%'
                    ) AS ht_ft_markets,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market LIKE 'first_half_%'
                    ) AS first_half_markets,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market LIKE 'second_half_%'
                    ) AS second_half_markets,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market LIKE 'asian_handicap_%'
                    ) AS asian_handicap_markets,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market LIKE 'exact_score_%'
                           OR market LIKE 'ht_ft_%'
                           OR market LIKE 'first_half_%'
                           OR market LIKE 'second_half_%'
                           OR market LIKE 'asian_handicap_%'
                    ) AS total_advanced_markets,

                    COUNT(DISTINCT match_id) AS matches_available,
                    COUNT(*) AS odds_rows
                FROM match_odds
                WHERE retrieved_at >= :since
                GROUP BY COALESCE(bookmaker, 'UNKNOWN')
                ORDER BY total_advanced_markets DESC, matches_available DESC
                LIMIT :limit
                """
            ),
            {"since": since, "limit": limit},
        ).mappings().all()

        return [dict(row) for row in rows]

    def same_bookmaker_grouping_readiness(
        self,
        since: datetime,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    COALESCE(bookmaker, 'UNKNOWN') AS bookmaker,
                    COUNT(DISTINCT match_id) AS matches_available,
                    COUNT(DISTINCT market) AS normalized_markets,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market IN (
                            'home_win',
                            'draw',
                            'away_win',
                            'over_1_5_goals',
                            'under_1_5_goals',
                            'over_2_5_goals',
                            'under_2_5_goals',
                            'over_3_5_goals',
                            'under_3_5_goals',
                            'btts_yes',
                            'btts_no',
                            'double_chance_1x',
                            'double_chance_x2',
                            'double_chance_12'
                        )
                    ) AS core_markets,

                    COUNT(DISTINCT market) FILTER (
                        WHERE market LIKE 'exact_score_%'
                           OR market LIKE 'ht_ft_%'
                           OR market LIKE 'first_half_%'
                           OR market LIKE 'second_half_%'
                           OR market LIKE 'asian_handicap_%'
                    ) AS advanced_markets,

                    ROUND(
                        COUNT(*)::numeric
                        / NULLIF(COUNT(DISTINCT match_id), 0),
                        4
                    ) AS odds_rows_per_match
                FROM match_odds
                WHERE retrieved_at >= :since
                GROUP BY COALESCE(bookmaker, 'UNKNOWN')
                ORDER BY matches_available DESC, normalized_markets DESC
                LIMIT :limit
                """
            ),
            {"since": since, "limit": limit},
        ).mappings().all()

        output = []

        for row in rows:
            matches_available = int(row["matches_available"] or 0)
            normalized_markets = int(row["normalized_markets"] or 0)
            core_markets = int(row["core_markets"] or 0)
            advanced_markets = int(row["advanced_markets"] or 0)
            odds_rows_per_match = float(row["odds_rows_per_match"] or 0.0)

            readiness_score = self._readiness_score(
                matches_available=matches_available,
                normalized_markets=normalized_markets,
                core_markets=core_markets,
                advanced_markets=advanced_markets,
                odds_rows_per_match=odds_rows_per_match,
            )

            output.append(
                {
                    "bookmaker": row["bookmaker"],
                    "matches_available": matches_available,
                    "normalized_markets": normalized_markets,
                    "core_markets": core_markets,
                    "advanced_markets": advanced_markets,
                    "odds_rows_per_match": odds_rows_per_match,
                    "same_bookmaker_readiness_score": readiness_score,
                    "readiness_tier": self._readiness_tier(readiness_score),
                }
            )

        output.sort(
            key=lambda item: item["same_bookmaker_readiness_score"],
            reverse=True,
        )

        return output[:limit]

    def _readiness_score(
        self,
        matches_available: int,
        normalized_markets: int,
        core_markets: int,
        advanced_markets: int,
        odds_rows_per_match: float,
    ) -> float:
        match_score = min(matches_available / 2000, 1.0) * 0.30
        market_score = min(normalized_markets / 220, 1.0) * 0.25
        core_score = min(core_markets / len(self.CORE_MARKETS), 1.0) * 0.25
        advanced_score = min(advanced_markets / 120, 1.0) * 0.15
        density_score = min(odds_rows_per_match / 200, 1.0) * 0.05

        return round(
            match_score
            + market_score
            + core_score
            + advanced_score
            + density_score,
            4,
        )

    def _readiness_tier(self, score: float) -> str:
        if score >= 0.85:
            return "GROUP_READY"

        if score >= 0.70:
            return "STRONG_CANDIDATE"

        if score >= 0.50:
            return "PARTIAL_SUPPORT"

        if score >= 0.30:
            return "LIMITED_SUPPORT"

        return "WEAK_SUPPORT"