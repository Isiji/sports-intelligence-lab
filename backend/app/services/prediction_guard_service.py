# backend/app/services/prediction_guard_service.py

from sqlalchemy.orm import Session

from app.db.models import (
    DynamicLeagueTier,
    LeagueIntelligenceSnapshot,
    LeagueMarketCoverageSnapshot,
    MarketIntelligenceSnapshot,
    Match,
)


DEFAULT_MIN_LEAGUE_SCORE = 0.30
DEFAULT_MIN_MARKET_SCORE = 0.45

BOOTSTRAP_ALLOW_IF_NO_INTELLIGENCE = True

MIN_MARKET_COVERAGE_RATE = 0.10


def clamp_multiplier(value: float) -> float:
    return max(
        0.72,
        min(value, 1.18),
    )


def evaluate_prediction_guard(
    session: Session,
    match: Match,
    market: str,
) -> dict:
    reasons: list[str] = []

    bootstrap_mode = False

    # =====================================================
    # LEAGUE INTELLIGENCE
    # =====================================================

    league_row = (
        session.query(LeagueIntelligenceSnapshot)
        .filter(
            LeagueIntelligenceSnapshot.league == match.league,
        )
        .first()
    )

    # =====================================================
    # MARKET INTELLIGENCE
    # =====================================================

    market_row = (
        session.query(MarketIntelligenceSnapshot)
        .filter(
            MarketIntelligenceSnapshot.market == market,
        )
        .first()
    )

    # =====================================================
    # MARKET COVERAGE
    # =====================================================

    coverage_row = (
        session.query(LeagueMarketCoverageSnapshot)
        .filter(
            LeagueMarketCoverageSnapshot.league == match.league,
            LeagueMarketCoverageSnapshot.market == market,
        )
        .first()
    )

    # =====================================================
    # DYNAMIC LEAGUE TIER
    # =====================================================

    dynamic_tier = (
        session.query(DynamicLeagueTier)
        .filter(
            DynamicLeagueTier.league == match.league,
        )
        .first()
    )

    # =====================================================
    # BOOTSTRAP MODE
    # =====================================================

    if (
        league_row is None
        and market_row is None
        and coverage_row is None
        and BOOTSTRAP_ALLOW_IF_NO_INTELLIGENCE
    ):
        bootstrap_mode = True

        return {
            "allowed": True,
            "bootstrap_mode": bootstrap_mode,
            "market": market,
            "match_id": match.id,
            "league": match.league,
            "league_multiplier": 1.0,
            "market_multiplier": 1.0,
            "coverage_multiplier": 1.0,
            "dynamic_league_multiplier": 1.0,
            "final_confidence_multiplier": 1.0,
            "reasons": [
                "bootstrap_mode_no_intelligence"
            ],
        }

    allowed = True

    league_multiplier = 1.0
    market_multiplier = 1.0
    coverage_multiplier = 1.0
    dynamic_league_multiplier = 1.0

    # =====================================================
    # LEAGUE EVALUATION
    # =====================================================

    if league_row is None:
        reasons.append(
            "No league intelligence available."
        )

        league_multiplier = 0.95

    else:
        league_multiplier = clamp_multiplier(
            float(
                league_row.confidence_multiplier or 1.0
            )
        )

        if (
            hasattr(league_row, "prediction_allowed")
            and league_row.prediction_allowed is False
        ):
            reasons.append(
                "League prediction is disabled."
            )

            league_multiplier *= 0.92

        league_score = float(
            getattr(
                league_row,
                "stats_quality_score",
                0.0,
            )
            or 0.0
        )

        if league_score < DEFAULT_MIN_LEAGUE_SCORE:
            reasons.append(
                "League stats quality is low."
            )

            league_multiplier *= 0.95

    # =====================================================
    # MARKET EVALUATION
    # =====================================================

    if market_row is None:
        reasons.append(
            "No market intelligence available."
        )

        market_multiplier = 0.96

    else:
        market_multiplier = clamp_multiplier(
            float(
                market_row.confidence_multiplier or 1.0
            )
        )

        if (
            hasattr(market_row, "prediction_allowed")
            and market_row.prediction_allowed is False
        ):
            reasons.append(
                "Market prediction is disabled."
            )

            market_multiplier *= 0.92

        market_score = float(
            getattr(
                market_row,
                "reliability_score",
                0.0,
            )
            or 0.0
        )

        if market_score < DEFAULT_MIN_MARKET_SCORE:
            reasons.append(
                "Market reliability is low."
            )

            market_multiplier *= 0.95

    # =====================================================
    # MARKET COVERAGE EVALUATION
    # =====================================================

    if coverage_row is None:
        reasons.append(
            "League-market coverage unavailable."
        )

        coverage_multiplier = 0.98

    else:
        coverage_rate = float(
            coverage_row.market_coverage_rate or 0.0
        )

        market_tier = (
            coverage_row.market_tier or "UNKNOWN"
        )

        bookmaker_count = int(
            coverage_row.bookmaker_count or 0
        )

        if (
            market_tier
            == "ELITE_MARKET_COVERAGE"
        ):
            coverage_multiplier = 1.05

        elif (
            market_tier
            == "STRONG_MARKET_COVERAGE"
        ):
            coverage_multiplier = 1.03

        elif (
            market_tier
            == "USABLE_MARKET_COVERAGE"
        ):
            coverage_multiplier = 1.0

        elif (
            market_tier
            == "LIMITED_MARKET_COVERAGE"
        ):
            coverage_multiplier = 0.96

        elif (
            market_tier
            == "POOR_MARKET_COVERAGE"
        ):
            coverage_multiplier = 0.90

        elif (
            market_tier
            == "INSUFFICIENT_SAMPLE"
        ):
            coverage_multiplier = 0.98

        else:
            coverage_multiplier = 0.95

        if coverage_rate < MIN_MARKET_COVERAGE_RATE:
            reasons.append(
                "Very low market coverage rate."
            )

            coverage_multiplier *= 0.92

        if bookmaker_count >= 10:
            coverage_multiplier += 0.01

        coverage_multiplier = clamp_multiplier(
            coverage_multiplier
        )

    # =====================================================
    # DYNAMIC LEAGUE TIER
    # =====================================================

    if dynamic_tier:
        tier = dynamic_tier.tier

        if tier == "VERY_STRONG":
            dynamic_league_multiplier = 1.06

        elif tier == "STRONG":
            dynamic_league_multiplier = 1.03

        elif tier == "WEAK":
            dynamic_league_multiplier = 0.94

        elif tier == "VERY_WEAK":
            dynamic_league_multiplier = 0.88

    # =====================================================
    # FINAL MULTIPLIER
    # =====================================================

    final_multiplier = (
        league_multiplier
        * market_multiplier
        * coverage_multiplier
        * dynamic_league_multiplier
    )

    final_multiplier = clamp_multiplier(
        round(final_multiplier, 4)
    )

    # =====================================================
    # HARD BLOCKS
    # =====================================================

    if coverage_row:
        if (
            coverage_row.market_tier
            == "POOR_MARKET_COVERAGE"
            and float(
                coverage_row.market_quality_score or 0.0
            )
            <= 15
        ):
            allowed = False

            reasons.append(
                "Market ecosystem quality too poor."
            )

    # =====================================================
    # RETURN
    # =====================================================

    return {
        "allowed": allowed,
        "bootstrap_mode": bootstrap_mode,
        "market": market,
        "match_id": match.id,
        "league": match.league,
        "league_multiplier": round(
            league_multiplier,
            4,
        ),
        "market_multiplier": round(
            market_multiplier,
            4,
        ),
        "coverage_multiplier": round(
            coverage_multiplier,
            4,
        ),
        "dynamic_league_multiplier": round(
            dynamic_league_multiplier,
            4,
        ),
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
        float(raw_confidence or 0.0)
        * float(
            guard["final_confidence_multiplier"]
        ),
        4,
    )

    adjusted_confidence = max(
        min(adjusted_confidence, 0.97),
        0.05,
    )

    return {
        **guard,
        "raw_confidence": raw_confidence,
        "adjusted_confidence": adjusted_confidence,
    }