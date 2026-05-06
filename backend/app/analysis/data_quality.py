# backend/app/analysis/data_quality.py

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.weak_markets import get_weak_markets
from app.features.football_features import MARKET_TARGETS


def training_readiness_report(session: Session) -> dict:
    played_matches = _count_played_matches(session)
    upcoming_matches = _count_upcoming_matches(session)

    stats_completeness = _stats_completeness(session)
    odds_completeness = _odds_completeness(session)

    leagues = _available_leagues(session)

    trainable_markets = _trainable_markets(
        session=session,
        minimum_matches=40,
    )

    weak_markets = get_weak_markets(session=session)

    recommendations = _recommendations(
        played_matches=played_matches,
        stats_completeness=stats_completeness,
        odds_completeness=odds_completeness,
        weak_markets=weak_markets,
    )

    return {
        "database_status": {
            "played_matches": played_matches,
            "upcoming_matches": upcoming_matches,
            "available_leagues": leagues,
        },

        "data_quality": {
            "stats_completeness": stats_completeness,
            "odds_completeness": odds_completeness,
        },

        "markets": {
            "trainable_markets": trainable_markets,
            "weak_markets": weak_markets,
        },

        "recommendations": recommendations,
    }


def _count_played_matches(session: Session) -> int:
    query = text(
        """
        SELECT COUNT(*)
        FROM matches
        WHERE home_goals IS NOT NULL
          AND away_goals IS NOT NULL
        """
    )

    return int(session.execute(query).scalar() or 0)


def _count_upcoming_matches(session: Session) -> int:
    query = text(
        """
        SELECT COUNT(*)
        FROM matches
        WHERE home_goals IS NULL
          AND away_goals IS NULL
        """
    )

    return int(session.execute(query).scalar() or 0)


def _stats_completeness(session: Session) -> dict:
    query = text(
        """
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN corners IS NOT NULL
                    THEN 1 ELSE 0
                END
            ) AS corners,

            SUM(
                CASE
                    WHEN shots_on_target IS NOT NULL
                    THEN 1 ELSE 0
                END
            ) AS sot,

            SUM(
                CASE
                    WHEN possession IS NOT NULL
                    THEN 1 ELSE 0
                END
            ) AS possession

        FROM team_match_stats
        """
    )

    row = session.execute(query).mappings().first()

    total = max(int(row["total"] or 1), 1)

    return {
        "corners_pct": round(row["corners"] / total, 4),
        "shots_on_target_pct": round(row["sot"] / total, 4),
        "possession_pct": round(row["possession"] / total, 4),
    }


def _odds_completeness(session: Session) -> dict:
    query = text(
        """
        SELECT
            COUNT(*) AS total_predictions,

            SUM(
                CASE
                    WHEN odds IS NOT NULL
                    THEN 1 ELSE 0
                END
            ) AS odds_available

        FROM predictions
        """
    )

    row = session.execute(query).mappings().first()

    total = max(int(row["total_predictions"] or 1), 1)

    return {
        "odds_coverage_pct": round(
            row["odds_available"] / total,
            4,
        ),
    }


def _available_leagues(session: Session) -> list[str]:
    query = text(
        """
        SELECT DISTINCT league
        FROM matches
        ORDER BY league ASC
        """
    )

    rows = session.execute(query).fetchall()

    return [row[0] for row in rows]


def _trainable_markets(
    session: Session,
    minimum_matches: int = 40,
) -> list[dict]:
    played_matches = _count_played_matches(session)

    markets = []

    for market in MARKET_TARGETS.keys():
        markets.append(
            {
                "market": market,
                "trainable": played_matches >= minimum_matches,
                "minimum_required_matches": minimum_matches,
                "available_matches": played_matches,
            }
        )

    return markets


def _recommendations(
    played_matches: int,
    stats_completeness: dict,
    odds_completeness: dict,
    weak_markets: list[dict],
) -> list[str]:
    recommendations = []

    if played_matches < 100:
        recommendations.append(
            "Collect more historical matches for stronger models."
        )

    if stats_completeness["shots_on_target_pct"] < 0.8:
        recommendations.append(
            "Improve shots-on-target coverage."
        )

    if stats_completeness["corners_pct"] < 0.8:
        recommendations.append(
            "Improve corners coverage."
        )

    if odds_completeness["odds_coverage_pct"] < 0.7:
        recommendations.append(
            "Collect more bookmaker odds."
        )

    if weak_markets:
        recommendations.append(
            "Disable or retrain weak-performing markets."
        )

    if not recommendations:
        recommendations.append(
            "System appears healthy and ready for real ingestion."
        )

    return recommendations