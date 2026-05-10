from sqlalchemy.orm import Session

from app.db.models import (
    ConfidenceBandIntelligenceSnapshot,
    LeagueIntelligenceSnapshot,
    LeagueMarketIntelligenceSnapshot,
    MarketIntelligenceSnapshot,
    Match,
    OddsBandIntelligenceSnapshot,
)
from app.services.confidence_recalibration_service import recalibrate_confidence


def resolve_odds_band(
    odds: float | None,
) -> str | None:
    if odds is None:
        return None

    if odds < 1.30:
        return "1.00-1.29"

    if odds < 1.50:
        return "1.30-1.49"

    if odds < 1.80:
        return "1.50-1.79"

    if odds < 2.20:
        return "1.80-2.19"

    if odds < 3.00:
        return "2.20-2.99"

    if odds < 5.00:
        return "3.00-4.99"

    return "5.00+"


def resolve_confidence_band(
    confidence: float,
) -> str:
    if confidence < 0.60:
        return "0.00-0.59"

    if confidence < 0.70:
        return "0.60-0.69"

    if confidence < 0.80:
        return "0.70-0.79"

    if confidence < 0.90:
        return "0.80-0.89"

    return "0.90+"


def apply_prediction_intelligence(
    session: Session,
    match: Match,
    market: str,
    raw_confidence: float,
    odds: float | None,
):
    confidence = float(raw_confidence or 0)

    reasons: list[str] = []
    allowed = True
    multiplier = 1.0

    market_row = (
        session.query(MarketIntelligenceSnapshot)
        .filter(
            MarketIntelligenceSnapshot.market == market,
        )
        .first()
    )

    if market_row:
        multiplier *= float(
            market_row.confidence_multiplier or 1.0
        )

        if not market_row.prediction_allowed:
            allowed = False
            reasons.append(
                "Market intelligence blocked prediction."
            )

    league_row = (
        session.query(LeagueIntelligenceSnapshot)
        .filter(
            LeagueIntelligenceSnapshot.league == match.league,
        )
        .first()
    )

    if league_row:
        multiplier *= float(
            league_row.confidence_multiplier or 1.0
        )

        if not league_row.prediction_allowed:
            allowed = False
            reasons.append(
                "League intelligence blocked prediction."
            )

    league_market_row = (
        session.query(LeagueMarketIntelligenceSnapshot)
        .filter(
            LeagueMarketIntelligenceSnapshot.league == match.league,
            LeagueMarketIntelligenceSnapshot.market == market,
        )
        .first()
    )

    if league_market_row:
        multiplier *= float(
            league_market_row.confidence_multiplier or 1.0
        )

        if not league_market_row.prediction_allowed:
            allowed = False
            reasons.append(
                "League-market intelligence blocked prediction."
            )

    odds_band = resolve_odds_band(odds)

    if odds_band:
        odds_row = (
            session.query(OddsBandIntelligenceSnapshot)
            .filter(
                OddsBandIntelligenceSnapshot.market == market,
                OddsBandIntelligenceSnapshot.odds_band == odds_band,
            )
            .first()
        )

        if odds_row:
            multiplier *= float(
                odds_row.confidence_multiplier or 1.0
            )

            if not odds_row.prediction_allowed:
                allowed = False
                reasons.append(
                    "Odds band intelligence blocked prediction."
                )

    confidence_band = resolve_confidence_band(confidence)

    confidence_row = (
        session.query(ConfidenceBandIntelligenceSnapshot)
        .filter(
            ConfidenceBandIntelligenceSnapshot.market == market,
            ConfidenceBandIntelligenceSnapshot.confidence_band == confidence_band,
        )
        .first()
    )

    if confidence_row:
        multiplier *= float(
            confidence_row.confidence_multiplier or 1.0
        )

        if not confidence_row.prediction_allowed:
            allowed = False
            reasons.append(
                "Confidence band intelligence blocked prediction."
            )

    adjusted_confidence = round(
        confidence * multiplier,
        4,
    )

    adjusted_confidence = max(
        min(adjusted_confidence, 0.99),
        0.01,
    )

    recalibration = recalibrate_confidence(
        session=session,
        market=market,
        confidence=adjusted_confidence,
    )

    final_confidence = float(
        recalibration["recalibrated_confidence"]
    )

    reasons.extend(
        recalibration.get("reasons", [])
    )

    return {
        "allowed": allowed,
        "raw_confidence": confidence,
        "adjusted_confidence": final_confidence,
        "pre_recalibration_confidence": adjusted_confidence,
        "multiplier": round(multiplier, 4),
        "recalibration": recalibration,
        "reasons": reasons,
        "league": match.league,
        "market": market,
        "odds_band": odds_band,
        "confidence_band": confidence_band,
    }