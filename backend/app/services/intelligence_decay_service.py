from sqlalchemy.orm import Session

from app.db.models import (
    LeagueIntelligenceSnapshot,
    LeagueMarketIntelligenceSnapshot,
    MarketIntelligenceSnapshot,
)


def calculate_decay_factor(
    bets: int,
    recent_roi: float,
    historical_roi: float,
):
    decay = 1.0

    if bets < 20:
        decay *= 0.75

    if recent_roi < historical_roi:
        decay *= 0.80

    if recent_roi < 0:
        decay *= 0.65

    return round(
        max(decay, 0.20),
        4,
    )


def apply_market_decay(
    session: Session,
):
    rows = session.query(
        MarketIntelligenceSnapshot
    ).all()

    updated = 0

    for row in rows:
        decay = calculate_decay_factor(
            bets=row.bets,
            recent_roi=row.recent_roi,
            historical_roi=row.roi,
        )

        row.decay_factor = decay

        row.confidence_multiplier = round(
            row.confidence_multiplier * decay,
            4,
        )

        row.stale = decay < 0.70

        if decay < 0.45:
            row.prediction_allowed = False

        updated += 1

    session.commit()

    return {
        "market_decay_updated": updated,
    }


def apply_league_decay(
    session: Session,
):
    rows = session.query(
        LeagueIntelligenceSnapshot
    ).all()

    updated = 0

    for row in rows:
        decay = calculate_decay_factor(
            bets=row.bets,
            recent_roi=row.recent_roi,
            historical_roi=row.roi,
        )

        row.decay_factor = decay

        row.confidence_multiplier = round(
            row.confidence_multiplier * decay,
            4,
        )

        row.stale = decay < 0.70

        if decay < 0.45:
            row.prediction_allowed = False

        updated += 1

    session.commit()

    return {
        "league_decay_updated": updated,
    }


def apply_league_market_decay(
    session: Session,
):
    rows = session.query(
        LeagueMarketIntelligenceSnapshot
    ).all()

    updated = 0

    for row in rows:
        decay = calculate_decay_factor(
            bets=row.bets,
            recent_roi=row.recent_roi,
            historical_roi=row.roi,
        )

        row.decay_factor = decay

        row.confidence_multiplier = round(
            row.confidence_multiplier * decay,
            4,
        )

        row.stale = decay < 0.70

        if decay < 0.45:
            row.prediction_allowed = False

        updated += 1

    session.commit()

    return {
        "league_market_decay_updated": updated,
    }