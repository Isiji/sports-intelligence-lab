# backend/app/services/prediction_guard_service.py

from sqlalchemy.orm import Session

from app.db.models import LeagueIntelligenceSnapshot, MarketReliabilitySnapshot, Match


DEFAULT_MIN_LEAGUE_SCORE = 0.30
DEFAULT_MIN_MARKET_SCORE = 0.45


def evaluate_prediction_guard(
    session: Session,
    match: Match,
    market: str,
) -> dict:
    league_row = (
        session.query(LeagueIntelligenceSnapshot)
        .filter(
            LeagueIntelligenceSnapshot.sport == match.sport,
            LeagueIntelligenceSnapshot.competition_id == match.competition_id,
            LeagueIntelligenceSnapshot.season == match.season,
        )
        .first()
    )

    market_row = (
        session.query(MarketReliabilitySnapshot)
        .filter(
            MarketReliabilitySnapshot.sport == match.sport,
            MarketReliabilitySnapshot.market == market,
        )
        .first()
    )

    allowed = True
    reasons: list[str] = []

    league_multiplier = 1.0
    market_multiplier = 1.0

    if league_row is None:
        allowed = False
        reasons.append("No league intelligence available.")
    else:
        league_multiplier = float(league_row.confidence_multiplier or 0.35)

        if not league_row.prediction_allowed:
            allowed = False
            reasons.append("League prediction is disabled.")

        if float(league_row.stats_quality_score or 0.0) < DEFAULT_MIN_LEAGUE_SCORE:
            allowed = False
            reasons.append("League stats quality is too low.")

    if market_row is None:
        allowed = False
        reasons.append("No market reliability available.")
    else:
        market_multiplier = float(market_row.confidence_multiplier or 0.35)

        if not market_row.prediction_allowed:
            allowed = False
            reasons.append("Market prediction is disabled.")

        if float(market_row.reliability_score or 0.0) < DEFAULT_MIN_MARKET_SCORE:
            allowed = False
            reasons.append("Market reliability is too low.")

    final_multiplier = round(league_multiplier * market_multiplier, 4)

    return {
        "allowed": allowed,
        "market": market,
        "match_id": match.id,
        "league": match.league,
        "league_multiplier": league_multiplier,
        "market_multiplier": market_multiplier,
        "final_confidence_multiplier": final_multiplier,
        "reasons": reasons,
    }


def apply_prediction_guard(
    session: Session,
    match: Match,
    market: str,
    raw_confidence: float,
) -> dict:
    guard = evaluate_prediction_guard(
        session=session,
        match=match,
        market=market,
    )

    adjusted_confidence = round(
        float(raw_confidence or 0.0) * guard["final_confidence_multiplier"],
        4,
    )

    return {
        **guard,
        "raw_confidence": raw_confidence,
        "adjusted_confidence": adjusted_confidence,
    }