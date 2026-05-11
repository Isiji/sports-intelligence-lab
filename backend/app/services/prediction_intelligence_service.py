# backend/app/services/prediction_intelligence_service.py

from sqlalchemy.orm import Session

from app.db.models import (
    BookmakerIntelligenceSnapshot,
    ConfidenceBandIntelligenceSnapshot,
    DynamicLeagueTier,
    LeagueIntelligenceSnapshot,
    LeagueMarketIntelligenceSnapshot,
    MarketFamilySnapshot,
    MarketIntelligenceSnapshot,
    Match,
    OddsBandIntelligenceSnapshot,
)
from app.services.confidence_recalibration_service import recalibrate_confidence

MIN_ALLOWED_CONFIDENCE_MULTIPLIER = 0.72
MAX_ALLOWED_CONFIDENCE_MULTIPLIER = 1.18

HARD_BLOCK_NEGATIVE_ROI = -0.35
SOFT_BLOCK_NEGATIVE_ROI = -0.15

MIN_SURVIVABILITY_SCORE = 6


def clamp_multiplier(value: float) -> float:
    return max(
        MIN_ALLOWED_CONFIDENCE_MULTIPLIER,
        min(
            value,
            MAX_ALLOWED_CONFIDENCE_MULTIPLIER,
        ),
    )


def resolve_market_family(
    market: str,
) -> str:
    market = market.lower()

    if (
        "over" in market
        or "under" in market
        or "goal" in market
        or "btts" in market
    ):
        return "GOALS"

    if "corner" in market:
        return "CORNERS"

    if "handicap" in market:
        return "HANDICAP"

    if (
        "win" in market
        or "draw" in market
        or "chance" in market
    ):
        return "RESULT"

    return "OTHER"


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


def _safe_float_attr(
    row,
    names: list[str],
    default: float = 0.0,
) -> float:
    for name in names:
        if hasattr(row, name):
            value = getattr(row, name)

            if value is not None:
                return float(value)

    return default


def _evaluate_market_row(
    row,
    scope: str,
    reasons: list[str],
) -> tuple[bool, float]:
    if not row:
        return True, 1.0

    multiplier = clamp_multiplier(
        _safe_float_attr(
            row,
            ["confidence_multiplier"],
            1.0,
        )
    )

    roi = _safe_float_attr(
        row,
        ["recent_roi", "roi"],
        0.0,
    )

    survivability = _safe_float_attr(
        row,
        ["survivability_score"],
        50.0,
    )

    if survivability < MIN_SURVIVABILITY_SCORE:
        reasons.append(
            f"{scope}: survivability too low"
        )

        return False, multiplier

    if roi <= HARD_BLOCK_NEGATIVE_ROI:
        reasons.append(
            f"{scope}: extremely negative ROI"
        )

        return False, multiplier

    if (
        hasattr(row, "prediction_allowed")
        and row.prediction_allowed is False
    ):
        if roi <= SOFT_BLOCK_NEGATIVE_ROI:
            reasons.append(
                f"{scope}: blocked by intelligence"
            )

            return False, multiplier

        reasons.append(
            f"{scope}: soft override applied"
        )

    return True, multiplier


def apply_prediction_intelligence(
    session: Session,
    match: Match,
    market: str,
    raw_confidence: float,
    odds: float | None,
    bookmaker: str | None = None,
):
    confidence = float(
        raw_confidence or 0
    )

    reasons: list[str] = []

    allowed = True

    multipliers: list[float] = []

    market_family = resolve_market_family(
        market
    )

    # =====================================================
    # MARKET
    # =====================================================

    market_row = (
        session.query(
            MarketIntelligenceSnapshot
        )
        .filter(
            MarketIntelligenceSnapshot.market
            == market
        )
        .first()
    )

    market_allowed, market_multiplier = (
        _evaluate_market_row(
            market_row,
            "market",
            reasons,
        )
    )

    if not market_allowed:
        allowed = False

    multipliers.append(
        market_multiplier
    )

    # =====================================================
    # LEAGUE
    # =====================================================

    league_row = (
        session.query(
            LeagueIntelligenceSnapshot
        )
        .filter(
            LeagueIntelligenceSnapshot.league
            == match.league
        )
        .first()
    )

    league_allowed, league_multiplier = (
        _evaluate_market_row(
            league_row,
            "league",
            reasons,
        )
    )

    if not league_allowed:
        allowed = False

    multipliers.append(
        league_multiplier
    )

    # =====================================================
    # LEAGUE MARKET
    # =====================================================

    league_market_row = (
        session.query(
            LeagueMarketIntelligenceSnapshot
        )
        .filter(
            LeagueMarketIntelligenceSnapshot.league
            == match.league,
            LeagueMarketIntelligenceSnapshot.market
            == market,
        )
        .first()
    )

    (
        league_market_allowed,
        league_market_multiplier,
    ) = _evaluate_market_row(
        league_market_row,
        "league_market",
        reasons,
    )

    if not league_market_allowed:
        allowed = False

    multipliers.append(
        league_market_multiplier
    )

    # =====================================================
    # ODDS BAND
    # =====================================================

    odds_band = resolve_odds_band(
        odds
    )

    if odds_band:
        odds_row = (
            session.query(
                OddsBandIntelligenceSnapshot
            )
            .filter(
                OddsBandIntelligenceSnapshot.market
                == market,
                OddsBandIntelligenceSnapshot.odds_band
                == odds_band,
            )
            .first()
        )

        odds_allowed, odds_multiplier = (
            _evaluate_market_row(
                odds_row,
                "odds_band",
                reasons,
            )
        )

        if not odds_allowed:
            allowed = False

        multipliers.append(
            odds_multiplier
        )

    # =====================================================
    # CONFIDENCE BAND
    # =====================================================

    confidence_band = (
        resolve_confidence_band(
            confidence
        )
    )

    confidence_row = (
        session.query(
            ConfidenceBandIntelligenceSnapshot
        )
        .filter(
            ConfidenceBandIntelligenceSnapshot.market
            == market,
            ConfidenceBandIntelligenceSnapshot.confidence_band
            == confidence_band,
        )
        .first()
    )

    (
        confidence_allowed,
        confidence_multiplier,
    ) = _evaluate_market_row(
        confidence_row,
        "confidence_band",
        reasons,
    )

    if not confidence_allowed:
        allowed = False

    multipliers.append(
        confidence_multiplier
    )

    # =====================================================
    # DYNAMIC LEAGUE TIER
    # =====================================================

    dynamic_league = (
        session.query(
            DynamicLeagueTier
        )
        .filter(
            DynamicLeagueTier.league
            == match.league
        )
        .first()
    )

    if dynamic_league:
        if (
            dynamic_league.tier
            == "VERY_STRONG"
        ):
            multipliers.append(1.08)

            reasons.append(
                "very_strong_league"
            )

        elif (
            dynamic_league.tier
            == "STRONG"
        ):
            multipliers.append(1.03)

            reasons.append(
                "strong_league"
            )

        elif (
            dynamic_league.tier
            == "WEAK"
        ):
            multipliers.append(0.92)

            reasons.append(
                "weak_league"
            )

    # =====================================================
    # MARKET FAMILY
    # =====================================================

    family_row = (
        session.query(
            MarketFamilySnapshot
        )
        .filter(
            MarketFamilySnapshot.family_name
            == market_family
        )
        .first()
    )

    if family_row:
        family_multiplier = float(
            family_row.confidence_multiplier
            or 1.0
        )

        multipliers.append(
            family_multiplier
        )

        reasons.append(
            f"market_family:{market_family}"
        )

    # =====================================================
    # BOOKMAKER INTELLIGENCE
    # =====================================================

    bookmaker_multiplier = 1.0

    if bookmaker:
        bookmaker_row = (
            session.query(
                BookmakerIntelligenceSnapshot
            )
            .filter(
                BookmakerIntelligenceSnapshot.bookmaker
                == bookmaker
            )
            .first()
        )

        if bookmaker_row:
            bookmaker_multiplier = float(
                bookmaker_row.confidence_multiplier
                or 1.0
            )

            multipliers.append(
                bookmaker_multiplier
            )

            reasons.append(
                f"bookmaker:{bookmaker}"
            )

    # =====================================================
    # FINAL MULTIPLIER
    # =====================================================

    if multipliers:
        combined_multiplier = (
            sum(multipliers)
            / len(multipliers)
        )

    else:
        combined_multiplier = 1.0

    combined_multiplier = clamp_multiplier(
        combined_multiplier
    )

    adjusted_confidence = round(
        confidence
        * combined_multiplier,
        4,
    )

    adjusted_confidence = max(
        min(adjusted_confidence, 0.97),
        0.05,
    )

    # =====================================================
    # RECALIBRATION
    # =====================================================

    recalibration = recalibrate_confidence(
        session=session,
        market=market,
        confidence=adjusted_confidence,
    )

    recalibrated_confidence = float(
        recalibration[
            "recalibrated_confidence"
        ]
    )

    final_confidence = max(
        recalibrated_confidence,
        confidence * 0.70,
    )

    final_confidence = round(
        min(final_confidence, 0.97),
        4,
    )

    reasons.extend(
        recalibration.get(
            "reasons",
            [],
        )
    )

    return {
        "allowed": allowed,
        "raw_confidence": confidence,
        "adjusted_confidence": final_confidence,
        "pre_recalibration_confidence": adjusted_confidence,
        "combined_multiplier": round(
            combined_multiplier,
            4,
        ),
        "multipliers": [
            round(x, 4)
            for x in multipliers
        ],
        "recalibration": recalibration,
        "reasons": reasons,
        "league": match.league,
        "market": market,
        "market_family": market_family,
        "bookmaker": bookmaker,
        "odds_band": odds_band,
        "confidence_band": confidence_band,
    }