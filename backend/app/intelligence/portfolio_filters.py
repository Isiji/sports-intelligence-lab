# backend/app/intelligence/portfolio_filters.py

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import (
    ConfidenceBandIntelligenceSnapshot,
    LeagueIntelligenceSnapshot,
    LeagueMarketIntelligenceSnapshot,
    MarketIntelligenceSnapshot,
    OddsBandIntelligenceSnapshot,
)
from app.odds.market_quality_engine import get_enabled_markets


@dataclass
class PortfolioFilterResult:
    allowed: bool
    reason: str
    risk_flags: list[str]
    risk_score: float
    tier: str


def _rejected(reason: str, flag: str) -> PortfolioFilterResult:
    return PortfolioFilterResult(
        allowed=False,
        reason=reason,
        risk_flags=[flag],
        risk_score=999.0,
        tier="REJECTED",
    )


def get_odds_band(odds: float | None) -> str:
    if odds is None:
        return "UNKNOWN"
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


def get_confidence_band(confidence: float | None) -> str:
    if confidence is None:
        return "UNKNOWN"
    if confidence < 0.60:
        return "0.00-0.59"
    if confidence < 0.70:
        return "0.60-0.69"
    if confidence < 0.80:
        return "0.70-0.79"
    if confidence < 0.90:
        return "0.80-0.89"
    return "0.90+"


def resolve_risk_tier(risk_score: float) -> str:
    if risk_score <= 12:
        return "SAFE"
    if risk_score <= 35:
        return "MODERATE"
    if risk_score <= 65:
        return "AGGRESSIVE"
    return "REJECTED"


def evaluate_pick_for_portfolio(
    *,
    session: Session | None = None,
    league: str | None,
    market: str,
    confidence: float | None,
    odds: float | None,
    value_score: float | None = None,
    strict: bool = True,
) -> PortfolioFilterResult:
    risk_flags: list[str] = []
    risk_score = 0.0

    selected_league = league or "UNKNOWN"
    selected_odds_band = get_odds_band(odds)
    selected_confidence_band = get_confidence_band(confidence)

    if session is not None:
        enabled_markets = set(get_enabled_markets(session))

        if market not in enabled_markets:
            return _rejected(
                "market disabled by odds quality engine",
                "MARKET_QUALITY_DISABLED",
            )

    if odds is None:
        return _rejected("missing odds", "NO_ODDS")

    if confidence is None:
        return _rejected("missing confidence", "NO_CONFIDENCE")

    if confidence < 0.60:
        risk_flags.append("VERY_LOW_CONFIDENCE")
        risk_score += 35
    elif confidence < 0.70:
        risk_flags.append("LOW_CONFIDENCE")
        risk_score += 18
    elif confidence >= 0.90:
        risk_flags.append("ELITE_CONFIDENCE")
        risk_score -= 8

    if odds > 4.50:
        risk_flags.append("EXTREME_ODDS")
        risk_score += 35
    elif odds > 3.00:
        risk_flags.append("HIGH_ODDS_VARIANCE")
        risk_score += 18
    elif odds < 1.20:
        risk_flags.append("VERY_LOW_ODDS")
        risk_score += 6

    if value_score is not None:
        if value_score < -0.15:
            risk_flags.append("VERY_NEGATIVE_VALUE_SCORE")
            risk_score += 40
        elif value_score < 0:
            risk_flags.append("NEGATIVE_VALUE_SCORE")
            risk_score += 15
        elif value_score >= 0.25:
            risk_flags.append("STRONG_VALUE_SCORE")
            risk_score -= 10
        elif value_score >= 0.15:
            risk_flags.append("GOOD_VALUE_SCORE")
            risk_score -= 5

    if session is not None:
        league_row = (
            session.query(LeagueIntelligenceSnapshot)
            .filter(LeagueIntelligenceSnapshot.league == selected_league)
            .first()
        )

        if league_row:
            if not league_row.prediction_allowed:
                return _rejected(
                    "league blocked by DB intelligence",
                    "DB_LEAGUE_BLOCKED",
                )

            if league_row.stale:
                risk_flags.append("STALE_LEAGUE_INTELLIGENCE")
                risk_score += 3

            if float(league_row.recent_roi or 0.0) < -0.10:
                risk_flags.append("NEGATIVE_RECENT_LEAGUE_ROI")
                risk_score += 12

            survivability = float(league_row.survivability_score or 0.0)

            if survivability < 10:
                risk_flags.append("VERY_LOW_LEAGUE_SURVIVABILITY")
                risk_score += 25
            elif survivability < 20:
                risk_flags.append("LOW_LEAGUE_SURVIVABILITY")
                risk_score += 12
            elif survivability >= 60:
                risk_flags.append("STRONG_LEAGUE_SURVIVABILITY")
                risk_score -= 8

            if league_row.safe_for_accumulators:
                risk_flags.append("SAFE_ACCUMULATOR_LEAGUE")
                risk_score -= 10

        market_row = (
            session.query(MarketIntelligenceSnapshot)
            .filter(MarketIntelligenceSnapshot.market == market)
            .first()
        )

        if market_row:
            if not market_row.prediction_allowed:
                return _rejected(
                    "market blocked by DB intelligence",
                    "DB_MARKET_BLOCKED",
                )

            if market_row.stale:
                risk_flags.append("STALE_MARKET_INTELLIGENCE")
                risk_score += 3

            if float(market_row.recent_roi or 0.0) < -0.10:
                risk_flags.append("NEGATIVE_RECENT_MARKET_ROI")
                risk_score += 12

            survivability = float(market_row.survivability_score or 0.0)

            if survivability < 10:
                risk_flags.append("VERY_LOW_MARKET_SURVIVABILITY")
                risk_score += 25
            elif survivability < 20:
                risk_flags.append("LOW_MARKET_SURVIVABILITY")
                risk_score += 12
            elif survivability >= 60:
                risk_flags.append("STRONG_MARKET_SURVIVABILITY")
                risk_score -= 8

        league_market_row = (
            session.query(LeagueMarketIntelligenceSnapshot)
            .filter(
                LeagueMarketIntelligenceSnapshot.league == selected_league,
                LeagueMarketIntelligenceSnapshot.market == market,
            )
            .first()
        )

        if league_market_row:
            if not league_market_row.prediction_allowed:
                return _rejected(
                    "league-market blocked by DB intelligence",
                    "DB_LEAGUE_MARKET_BLOCKED",
                )

            if league_market_row.stale:
                risk_flags.append("STALE_LEAGUE_MARKET")
                risk_score += 3

            if float(league_market_row.recent_roi or 0.0) < -0.10:
                risk_flags.append("NEGATIVE_LEAGUE_MARKET_ROI")
                risk_score += 15

            survivability = float(league_market_row.survivability_score or 0.0)

            if survivability < 10:
                risk_flags.append("VERY_LOW_LEAGUE_MARKET_SURVIVABILITY")
                risk_score += 25
            elif survivability < 20:
                risk_flags.append("LOW_LEAGUE_MARKET_SURVIVABILITY")
                risk_score += 12
            elif survivability >= 60:
                risk_flags.append("STRONG_LEAGUE_MARKET_SURVIVABILITY")
                risk_score -= 8

        odds_row = (
            session.query(OddsBandIntelligenceSnapshot)
            .filter(
                OddsBandIntelligenceSnapshot.market == market,
                OddsBandIntelligenceSnapshot.odds_band == selected_odds_band,
            )
            .first()
        )

        if odds_row:
            if not odds_row.prediction_allowed:
                return _rejected(
                    "odds band blocked by DB intelligence",
                    "DB_ODDS_BAND_BLOCKED",
                )

            if float(odds_row.roi or 0.0) < -0.15:
                risk_flags.append("NEGATIVE_ODDS_BAND_ROI")
                risk_score += 10

        confidence_row = (
            session.query(ConfidenceBandIntelligenceSnapshot)
            .filter(
                ConfidenceBandIntelligenceSnapshot.market == market,
                ConfidenceBandIntelligenceSnapshot.confidence_band == selected_confidence_band,
            )
            .first()
        )

        if confidence_row:
            if not confidence_row.prediction_allowed:
                return _rejected(
                    "confidence band blocked by DB intelligence",
                    "DB_CONFIDENCE_BAND_BLOCKED",
                )

            if float(confidence_row.roi or 0.0) < -0.15:
                risk_flags.append("NEGATIVE_CONFIDENCE_BAND_ROI")
                risk_score += 10

    risk_score = round(max(risk_score, 0.0), 2)
    tier = resolve_risk_tier(risk_score)
    allowed = tier != "REJECTED"

    return PortfolioFilterResult(
        allowed=allowed,
        reason=f"{tier.lower()} portfolio tier",
        risk_flags=sorted(set(risk_flags)),
        risk_score=risk_score,
        tier=tier,
    )