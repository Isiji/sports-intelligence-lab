# backend/app/services/prediction_intelligence_service.py

from sqlalchemy.orm import Session

from app.db.models import (
    BookmakerIntelligenceSnapshot,
    ConfidenceBandIntelligenceSnapshot,
    DynamicLeagueTier,
    LeagueIntelligenceSnapshot,
    LeagueMarketCoverageSnapshot,
    LeagueMarketIntelligenceSnapshot,
    MarketFamilySnapshot,
    MarketIntelligenceSnapshot,
    Match,
    OddsBandIntelligenceSnapshot,
)
from app.odds.executable_market_registry import (
    get_market_family,
    parse_executable_market,
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
    confidence = float(raw_confidence or 0)

    reasons: list[str] = []
    allowed = True
    multipliers: list[float] = []

    executable = parse_executable_market(
        market
    )

    market_family = executable.family

    # =====================================================
    # EXECUTION RISK
    # =====================================================

    if executable.execution_risk == "HIGH":
        multipliers.append(0.92)
        reasons.append("high_execution_risk")

    elif executable.execution_risk == "MEDIUM":
        multipliers.append(0.97)
        reasons.append("medium_execution_risk")

    # =====================================================
    # VOLATILITY
    # =====================================================

    if executable.volatility_tier == "EXTREME":
        multipliers.append(0.90)
        reasons.append("extreme_market_volatility")

    elif executable.volatility_tier == "HIGH":
        multipliers.append(0.95)
        reasons.append("high_market_volatility")

    # =====================================================
    # PRODUCTION ELIGIBILITY
    # =====================================================

    if not executable.production_ready:
        allowed = False
        reasons.append("market_not_production_ready")

    # =====================================================
    # MARKET
    # =====================================================

    market_row = (
        session.query(MarketIntelligenceSnapshot)
        .filter(MarketIntelligenceSnapshot.market == market)
        .first()
    )

    market_allowed, market_multiplier = _evaluate_market_row(
        market_row,
        "market",
        reasons,
    )

    if not market_allowed:
        allowed = False

    multipliers.append(market_multiplier)

    # =====================================================
    # LEAGUE
    # =====================================================

    league_row = (
        session.query(LeagueIntelligenceSnapshot)
        .filter(LeagueIntelligenceSnapshot.league == match.league)
        .first()
    )

    league_allowed, league_multiplier = _evaluate_market_row(
        league_row,
        "league",
        reasons,
    )

    if not league_allowed:
        allowed = False

    multipliers.append(league_multiplier)

    # =====================================================
    # LEAGUE MARKET
    # =====================================================

    league_market_row = (
        session.query(LeagueMarketIntelligenceSnapshot)
        .filter(
            LeagueMarketIntelligenceSnapshot.league == match.league,
            LeagueMarketIntelligenceSnapshot.market == market,
        )
        .first()
    )

    league_market_allowed, league_market_multiplier = _evaluate_market_row(
        league_market_row,
        "league_market",
        reasons,
    )

    if not league_market_allowed:
        allowed = False

    multipliers.append(league_market_multiplier)

    # =====================================================
    # COVERAGE
    # =====================================================

    league_market_coverage = (
        session.query(LeagueMarketCoverageSnapshot)
        .filter(
            LeagueMarketCoverageSnapshot.league == match.league,
            LeagueMarketCoverageSnapshot.market == market,
        )
        .first()
    )

    if league_market_coverage:
        coverage_multiplier = 1.0

        market_tier = league_market_coverage.market_tier

        if market_tier == "ELITE_MARKET_COVERAGE":
            coverage_multiplier = 1.05

        elif market_tier == "STRONG_MARKET_COVERAGE":
            coverage_multiplier = 1.03

        elif market_tier == "USABLE_MARKET_COVERAGE":
            coverage_multiplier = 1.0

        elif market_tier == "LIMITED_MARKET_COVERAGE":
            coverage_multiplier = 0.96

        elif market_tier == "POOR_MARKET_COVERAGE":
            coverage_multiplier = 0.90

        coverage_multiplier = clamp_multiplier(
            coverage_multiplier
        )

        multipliers.append(
            coverage_multiplier
        )

    # =====================================================
    # ODDS BAND
    # =====================================================

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

        odds_allowed, odds_multiplier = _evaluate_market_row(
            odds_row,
            "odds_band",
            reasons,
        )

        if not odds_allowed:
            allowed = False

        multipliers.append(
            odds_multiplier
        )

    # =====================================================
    # CONFIDENCE BAND
    # =====================================================

    confidence_band = resolve_confidence_band(
        confidence
    )

    confidence_row = (
        session.query(ConfidenceBandIntelligenceSnapshot)
        .filter(
            ConfidenceBandIntelligenceSnapshot.market == market,
            ConfidenceBandIntelligenceSnapshot.confidence_band == confidence_band,
        )
        .first()
    )

    confidence_allowed, confidence_multiplier = _evaluate_market_row(
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
    # LEAGUE TIER
    # =====================================================

    dynamic_league = (
        session.query(DynamicLeagueTier)
        .filter(DynamicLeagueTier.league == match.league)
        .first()
    )

    if dynamic_league:
        if dynamic_league.tier == "VERY_STRONG":
            multipliers.append(1.08)

        elif dynamic_league.tier == "STRONG":
            multipliers.append(1.03)

        elif dynamic_league.tier == "WEAK":
            multipliers.append(0.92)

    # =====================================================
    # FAMILY
    # =====================================================

    family_row = (
        session.query(MarketFamilySnapshot)
        .filter(
            MarketFamilySnapshot.family_name == market_family
        )
        .first()
    )

    if family_row:
        family_multiplier = float(
            family_row.confidence_multiplier or 1.0
        )

        multipliers.append(
            family_multiplier
        )

    # =====================================================
    # BOOKMAKER
    # =====================================================

    if bookmaker:
        bookmaker_row = (
            session.query(BookmakerIntelligenceSnapshot)
            .filter(
                BookmakerIntelligenceSnapshot.bookmaker == bookmaker
            )
            .first()
        )

        if bookmaker_row:
            multipliers.append(
                float(
                    bookmaker_row.confidence_multiplier or 1.0
                )
            )

    # =====================================================
    # FINAL
    # =====================================================

    combined_multiplier = (
        sum(multipliers) / len(multipliers)
        if multipliers
        else 1.0
    )

    combined_multiplier = clamp_multiplier(
        combined_multiplier
    )

    adjusted_confidence = round(
        confidence * combined_multiplier,
        4,
    )

    adjusted_confidence = max(
        min(adjusted_confidence, 0.97),
        0.05,
    )

    recalibration = recalibrate_confidence(
        session=session,
        market=market,
        confidence=adjusted_confidence,
    )

    recalibrated_confidence = float(
        recalibration["recalibrated_confidence"]
    )

    final_confidence = max(
        recalibrated_confidence,
        confidence * 0.70,
    )

    final_confidence = round(
        min(final_confidence, 0.97),
        4,
    )

    return {
        "allowed": allowed,
        "raw_confidence": confidence,
        "adjusted_confidence": final_confidence,
        "combined_multiplier": round(combined_multiplier, 4),
        "market_family": market_family,
        "execution_risk": executable.execution_risk,
        "volatility_tier": executable.volatility_tier,
        "scope": executable.scope,
        "side": executable.side,
        "line": executable.line,
        "reasons": reasons,
    }