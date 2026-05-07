# backend/app/services/stats_quality_service.py

from datetime import datetime

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models import Match, StatsQualitySnapshot, TeamMatchStat


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _sample_size_score(finished_matches: int) -> float:
    if finished_matches >= 300:
        return 1.0
    if finished_matches >= 150:
        return 0.85
    if finished_matches >= 75:
        return 0.65
    if finished_matches >= 30:
        return 0.4
    if finished_matches >= 10:
        return 0.2
    return 0.05


def _quality_tier(score: float) -> str:
    if score >= 0.85:
        return "excellent"
    if score >= 0.70:
        return "good"
    if score >= 0.50:
        return "medium"
    if score >= 0.30:
        return "weak"
    return "poor"


def rebuild_stats_quality_snapshots(session: Session) -> dict:
    groups = (
        session.query(
            Match.sport,
            Match.league,
            Match.season,
            Match.competition_id,
            func.count(Match.id).label("finished_matches"),
            func.sum(case((Match.has_stats.is_(True), 1), else_=0)).label(
                "matches_with_stats"
            ),
            func.sum(case((Match.has_odds.is_(True), 1), else_=0)).label(
                "matches_with_odds"
            ),
        )
        .filter(Match.is_finished.is_(True))
        .group_by(
            Match.sport,
            Match.league,
            Match.season,
            Match.competition_id,
        )
        .all()
    )

    updated = 0

    for row in groups:
        sport = row.sport or "football"
        league = row.league
        season = row.season
        competition_id = row.competition_id

        finished_matches = int(row.finished_matches or 0)
        matches_with_stats = int(row.matches_with_stats or 0)
        matches_with_odds = int(row.matches_with_odds or 0)

        match_ids_query = session.query(Match.id).filter(
            Match.is_finished.is_(True),
            Match.sport == sport,
            Match.league == league,
            Match.season == season,
        )

        stat_rows = (
            session.query(func.count(TeamMatchStat.id))
            .filter(TeamMatchStat.match_id.in_(match_ids_query))
            .scalar()
            or 0
        )

        real_stat_rows = (
            session.query(func.count(TeamMatchStat.id))
            .filter(
                TeamMatchStat.match_id.in_(match_ids_query),
                TeamMatchStat.is_real.is_(True),
            )
            .scalar()
            or 0
        )

        matches_with_real_stats = (
            session.query(func.count(func.distinct(TeamMatchStat.match_id)))
            .filter(
                TeamMatchStat.match_id.in_(match_ids_query),
                TeamMatchStat.is_real.is_(True),
            )
            .scalar()
            or 0
        )

        coverage_score = _safe_ratio(matches_with_stats, finished_matches)
        realness_score = _safe_ratio(matches_with_real_stats, finished_matches)
        odds_score = _safe_ratio(matches_with_odds, finished_matches)
        sample_score = _sample_size_score(finished_matches)

        overall_score = round(
            (
                coverage_score * 0.30
                + realness_score * 0.35
                + odds_score * 0.20
                + sample_score * 0.15
            ),
            4,
        )

        tier = _quality_tier(overall_score)

        notes = (
            f"Coverage={coverage_score}, "
            f"real_stats={realness_score}, "
            f"odds={odds_score}, "
            f"sample_size={sample_score}"
        )

        snapshot = (
            session.query(StatsQualitySnapshot)
            .filter(
                StatsQualitySnapshot.sport == sport,
                StatsQualitySnapshot.competition_id == competition_id,
                StatsQualitySnapshot.season == season,
            )
            .first()
        )

        if snapshot is None:
            snapshot = StatsQualitySnapshot(
                sport=sport,
                league=league,
                season=season,
                competition_id=competition_id,
                created_at=datetime.utcnow(),
            )
            session.add(snapshot)

        snapshot.competition_id = competition_id
        snapshot.finished_matches = finished_matches
        snapshot.matches_with_stats = matches_with_stats
        snapshot.matches_with_real_stats = int(matches_with_real_stats)
        snapshot.matches_with_odds = matches_with_odds
        snapshot.stat_rows = int(stat_rows)
        snapshot.real_stat_rows = int(real_stat_rows)
        snapshot.coverage_score = coverage_score
        snapshot.realness_score = realness_score
        snapshot.odds_score = odds_score
        snapshot.sample_size_score = sample_score
        snapshot.overall_score = overall_score
        snapshot.quality_tier = tier
        snapshot.notes = notes
        snapshot.updated_at = datetime.utcnow()

        updated += 1

    session.commit()

    return {
        "message": "Stats quality snapshots rebuilt successfully.",
        "snapshots_updated": updated,
    }


def list_stats_quality_snapshots(
    session: Session,
    limit: int = 100,
    min_score: float | None = None,
    tier: str | None = None,
) -> list[dict]:
    query = session.query(StatsQualitySnapshot)

    if min_score is not None:
        query = query.filter(StatsQualitySnapshot.overall_score >= min_score)

    if tier:
        query = query.filter(StatsQualitySnapshot.quality_tier == tier)

    rows = (
        query.order_by(
            StatsQualitySnapshot.overall_score.desc(),
            StatsQualitySnapshot.finished_matches.desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "sport": row.sport,
            "league": row.league,
            "season": row.season,
            "competition_id": row.competition_id,
            "finished_matches": row.finished_matches,
            "matches_with_stats": row.matches_with_stats,
            "matches_with_real_stats": row.matches_with_real_stats,
            "matches_with_odds": row.matches_with_odds,
            "stat_rows": row.stat_rows,
            "real_stat_rows": row.real_stat_rows,
            "coverage_score": row.coverage_score,
            "realness_score": row.realness_score,
            "odds_score": row.odds_score,
            "sample_size_score": row.sample_size_score,
            "overall_score": row.overall_score,
            "quality_tier": row.quality_tier,
            "notes": row.notes,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]