# backend/app/services/league_intelligence_service.py

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import LeagueIntelligenceSnapshot, StatsQualitySnapshot


def _risk_level(score: float) -> str:
    if score >= 0.85:
        return "very_low"
    if score >= 0.70:
        return "low"
    if score >= 0.50:
        return "medium"
    if score >= 0.30:
        return "high"
    return "very_high"


def _confidence_multiplier(score: float) -> float:
    if score >= 0.85:
        return 1.0
    if score >= 0.70:
        return 0.9
    if score >= 0.50:
        return 0.75
    if score >= 0.30:
        return 0.55
    return 0.35


def _prediction_allowed(score: float) -> bool:
    return score >= 0.30


def _training_allowed(score: float, finished_matches: int) -> bool:
    return score >= 0.50 and finished_matches >= 75


def rebuild_league_intelligence(session: Session) -> dict:
    snapshots = session.query(StatsQualitySnapshot).all()

    updated = 0

    for stats in snapshots:
        score = float(stats.overall_score or 0.0)
        finished_matches = int(stats.finished_matches or 0)

        prediction_allowed = _prediction_allowed(score)
        training_allowed = _training_allowed(score, finished_matches)

        risk_level = _risk_level(score)
        confidence_multiplier = _confidence_multiplier(score)

        reason = (
            f"Stats quality={score}, tier={stats.quality_tier}, "
            f"finished_matches={finished_matches}, "
            f"realness={stats.realness_score}, odds={stats.odds_score}"
        )

        row = (
            session.query(LeagueIntelligenceSnapshot)
            .filter(
                LeagueIntelligenceSnapshot.sport == stats.sport,
                LeagueIntelligenceSnapshot.competition_id == stats.competition_id,
                LeagueIntelligenceSnapshot.season == stats.season,
            )
            .first()
        )

        if row is None:
            row = LeagueIntelligenceSnapshot(
                sport=stats.sport,
                competition_id=stats.competition_id,
                league=stats.league,
                season=stats.season,
                created_at=datetime.utcnow(),
            )
            session.add(row)

        row.league = stats.league
        row.stats_quality_score = score
        row.data_tier = stats.quality_tier
        row.prediction_allowed = prediction_allowed
        row.training_allowed = training_allowed
        row.confidence_multiplier = confidence_multiplier
        row.risk_level = risk_level
        row.reason = reason
        row.updated_at = datetime.utcnow()

        updated += 1

    session.commit()

    return {
        "message": "League intelligence rebuilt successfully.",
        "leagues_updated": updated,
    }


def list_league_intelligence(
    session: Session,
    limit: int = 100,
    prediction_allowed: bool | None = None,
    training_allowed: bool | None = None,
    risk_level: str | None = None,
) -> list[dict]:
    query = session.query(LeagueIntelligenceSnapshot)

    if prediction_allowed is not None:
        query = query.filter(
            LeagueIntelligenceSnapshot.prediction_allowed.is_(prediction_allowed)
        )

    if training_allowed is not None:
        query = query.filter(
            LeagueIntelligenceSnapshot.training_allowed.is_(training_allowed)
        )

    if risk_level:
        query = query.filter(LeagueIntelligenceSnapshot.risk_level == risk_level)

    rows = (
        query.order_by(
            LeagueIntelligenceSnapshot.stats_quality_score.desc(),
            LeagueIntelligenceSnapshot.league.asc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "sport": row.sport,
            "competition_id": row.competition_id,
            "league": row.league,
            "season": row.season,
            "stats_quality_score": row.stats_quality_score,
            "data_tier": row.data_tier,
            "prediction_allowed": row.prediction_allowed,
            "training_allowed": row.training_allowed,
            "confidence_multiplier": row.confidence_multiplier,
            "risk_level": row.risk_level,
            "reason": row.reason,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]