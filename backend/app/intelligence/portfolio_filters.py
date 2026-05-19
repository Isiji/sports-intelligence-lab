# backend/app/intelligence/portfolio_filters.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    ConfidenceBandIntelligenceSnapshot,
    DynamicLeagueTier,
    LeagueIntelligenceSnapshot,
    LeagueMarketIntelligenceSnapshot,
    MarketFamilySnapshot,
    MarketIntelligenceSnapshot,
    OddsBandIntelligenceSnapshot,
)
from app.odds.executable_market_registry import parse_executable_market
from app.odds.market_quality_engine import get_enabled_markets


@dataclass
class PortfolioFilterResult:
    allowed: bool
    reason: str
    risk_flags: list[str]
    risk_score: float
    tier: str


@dataclass(frozen=True)
class PortfolioFilterContext:
    enabled_markets: set[str]
    leagues: dict[str, Any]
    markets: dict[str, Any]
    league_markets: dict[tuple[str, str], Any]
    odds_bands: dict[tuple[str, str], Any]
    confidence_bands: dict[tuple[str, str], Any]
    league_tiers: dict[str, Any]
    market_families: dict[str, Any]


STRICT_MIN_CONFIDENCE = 0.60
STRICT_MIN_VALUE_SCORE = 0.03

STRICT_MAX_ODDS = 4.20
STRICT_MIN_ODDS = 1.30

HARD_BLOCK_ROI = -0.30
HARD_BLOCK_SURVIVABILITY = 8
SAFE_SURVIVABILITY = 60

MAX_ACCEPTABLE_RISK_SCORE = 42.0


def _rejected(reason: str, flag: str) -> PortfolioFilterResult:
    return PortfolioFilterResult(
        allowed=False,
        reason=reason,
        risk_flags=[flag],
        risk_score=999.0,
        tier="REJECTED",
    )


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _row_float(row: Any, *names: str, default: float = 0.0) -> float:
    for name in names:
        if hasattr(row, name):
            return _float_value(getattr(row, name), default)
    return default


def _row_str(row: Any, *names: str, default: str = "") -> str:
    for name in names:
        if hasattr(row, name):
            value = getattr(row, name)
            if value is not None:
                return str(value)
    return default


def _is_strong_exact_executable_pick(
    *,
    confidence: float | None,
    odds: float | None,
    value_score: float | None,
    market: str,
) -> bool:
    executable = parse_executable_market(market)

    if executable.volatility_tier == "EXTREME":
        return False

    selected_confidence = _float_value(confidence)
    selected_odds = _float_value(odds)
    selected_value = _float_value(value_score)

    return (
        selected_confidence >= 0.64
        and selected_value >= 0.06
        and STRICT_MIN_ODDS <= selected_odds <= STRICT_MAX_ODDS
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
    if risk_score <= 28:
        return "MODERATE"
    if risk_score <= MAX_ACCEPTABLE_RISK_SCORE:
        return "AGGRESSIVE"
    return "REJECTED"


def resolve_market_family(market: str) -> str:
    return parse_executable_market(market).family


def build_portfolio_filter_context(session: Session) -> PortfolioFilterContext:
    return PortfolioFilterContext(
        enabled_markets=set(get_enabled_markets(session)),
        leagues={row.league: row for row in session.query(LeagueIntelligenceSnapshot).all()},
        markets={row.market: row for row in session.query(MarketIntelligenceSnapshot).all()},
        league_markets={
            (row.league, row.market): row
            for row in session.query(LeagueMarketIntelligenceSnapshot).all()
        },
        odds_bands={
            (row.market, row.odds_band): row
            for row in session.query(OddsBandIntelligenceSnapshot).all()
        },
        confidence_bands={
            (row.market, row.confidence_band): row
            for row in session.query(ConfidenceBandIntelligenceSnapshot).all()
        },
        league_tiers={row.league: row for row in session.query(DynamicLeagueTier).all()},
        market_families={
            row.family_name: row
            for row in session.query(MarketFamilySnapshot).all()
        },
    )


def evaluate_pick_for_portfolio(
    *,
    session: Session | None = None,
    context: PortfolioFilterContext | None = None,
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
    selected_market = market
    selected_market_family = parse_executable_market(selected_market).family
    selected_odds_band = get_odds_band(odds)
    selected_confidence_band = get_confidence_band(confidence)
    executable = parse_executable_market(selected_market)

    strong_exact_executable = _is_strong_exact_executable_pick(
        confidence=confidence,
        odds=odds,
        value_score=value_score,
        market=selected_market,
    )

    if context is None and session is not None:
        context = build_portfolio_filter_context(session)

    if context is not None and selected_market not in context.enabled_markets:
        return _rejected("market disabled by quality engine", "MARKET_DISABLED")

    if odds is None:
        return _rejected("missing odds", "NO_ODDS")
    if confidence is None:
        return _rejected("missing confidence", "NO_CONFIDENCE")
    if odds <= 1.01:
        return _rejected("invalid odds", "INVALID_ODDS")
    if odds > STRICT_MAX_ODDS:
        return _rejected("high variance odds rejected", "EXTREME_ODDS")
    if odds < STRICT_MIN_ODDS:
        return _rejected("odds too low", "LOW_ODDS")
    if confidence < STRICT_MIN_CONFIDENCE:
        return _rejected("confidence below strict threshold", "LOW_CONFIDENCE")
    if value_score is not None and value_score < STRICT_MIN_VALUE_SCORE:
        return _rejected("value score below strict threshold", "LOW_VALUE_SCORE")

    if executable.volatility_tier == "EXTREME":
        return _rejected("extreme volatility blocked", "EXTREME_VOLATILITY")

    if executable.family in {"EXACT_SCORE", "HT_FT"}:
        return _rejected("derivative family blocked", "DERIVATIVE_BLOCKED")

    if executable.execution_risk == "HIGH":
        risk_score += 10
        risk_flags.append("HIGH_EXECUTION_RISK_PENALTY")

    if confidence < 0.64:
        risk_flags.append("MEDIUM_CONFIDENCE")
        risk_score += 12
    elif confidence >= 0.90:
        risk_flags.append("ELITE_CONFIDENCE")
        risk_score -= 12
    elif confidence >= 0.82:
        risk_flags.append("HIGH_CONFIDENCE")
        risk_score -= 8

    if odds > 3.20:
        risk_flags.append("HIGH_VARIANCE_ODDS")
        risk_score += 16
    elif odds > 2.50:
        risk_flags.append("MODERATE_VARIANCE_ODDS")
        risk_score += 8
    elif 1.35 <= odds <= 2.20:
        risk_flags.append("GOOD_PRODUCTION_ODDS")
        risk_score -= 5

    if value_score is not None:
        if value_score >= 0.25:
            risk_flags.append("ELITE_VALUE")
            risk_score -= 16
        elif value_score >= 0.15:
            risk_flags.append("GOOD_VALUE")
            risk_score -= 10
        elif value_score >= 0.08:
            risk_flags.append("POSITIVE_VALUE")
            risk_score -= 4

    if context is not None:
        league_row = context.leagues.get(selected_league)

        if league_row:
            league_roi = _row_float(league_row, "recent_roi", "roi")
            league_survivability = _row_float(
                league_row,
                "survivability_score",
                "survivability",
            )

            if league_roi <= HARD_BLOCK_ROI or league_survivability < HARD_BLOCK_SURVIVABILITY:
                return _rejected("league hard blocked", "LEAGUE_HARD_BLOCK")

            if league_survivability >= SAFE_SURVIVABILITY:
                risk_score -= 10
                risk_flags.append("SAFE_LEAGUE")
            elif league_survivability < 20:
                risk_score += 12
                risk_flags.append("WEAK_LEAGUE")
        else:
            risk_score += 8
            risk_flags.append("MISSING_LEAGUE_INTELLIGENCE")

        market_row = context.markets.get(selected_market)

        if market_row:
            market_roi = _row_float(market_row, "recent_roi", "roi")
            market_survivability = _row_float(
                market_row,
                "survivability_score",
                "survivability",
            )

            if market_roi <= HARD_BLOCK_ROI or market_survivability < HARD_BLOCK_SURVIVABILITY:
                return _rejected("market hard blocked", "MARKET_HARD_BLOCK")

            if market_survivability >= SAFE_SURVIVABILITY:
                risk_score -= 10
                risk_flags.append("SAFE_MARKET")
            elif market_survivability < 20:
                risk_score += 10
                risk_flags.append("WEAK_MARKET")
        else:
            if strong_exact_executable:
                risk_score += 8
                risk_flags.append("MISSING_MARKET_INTELLIGENCE_PENALTY")
            else:
                return _rejected(
                    "missing market intelligence for non-strong executable pick",
                    "MISSING_MARKET_INTELLIGENCE",
                )

        league_market_row = context.league_markets.get((selected_league, selected_market))

        if league_market_row:
            league_market_roi = _row_float(league_market_row, "recent_roi", "roi")
            league_market_survivability = _row_float(
                league_market_row,
                "survivability_score",
                "survivability",
            )

            if (
                league_market_roi <= HARD_BLOCK_ROI
                or league_market_survivability < HARD_BLOCK_SURVIVABILITY
            ):
                return _rejected(
                    "league-market hard blocked",
                    "LEAGUE_MARKET_HARD_BLOCK",
                )

            if league_market_survivability >= SAFE_SURVIVABILITY:
                risk_score -= 12
                risk_flags.append("SAFE_LEAGUE_MARKET")
            elif league_market_survivability < 20:
                risk_score += 12
                risk_flags.append("WEAK_LEAGUE_MARKET")
        else:
            if strong_exact_executable:
                risk_score += 10
                risk_flags.append("MISSING_LEAGUE_MARKET_INTELLIGENCE_PENALTY")
            else:
                return _rejected(
                    "missing league-market intelligence for non-strong executable pick",
                    "MISSING_LEAGUE_MARKET_INTELLIGENCE",
                )

        odds_band_row = context.odds_bands.get((selected_market, selected_odds_band))

        if odds_band_row:
            odds_band_roi = _row_float(odds_band_row, "recent_roi", "roi")
            odds_band_survivability = _row_float(
                odds_band_row,
                "survivability_score",
                "survivability",
            )

            if odds_band_roi <= HARD_BLOCK_ROI or odds_band_survivability < HARD_BLOCK_SURVIVABILITY:
                return _rejected("odds-band hard blocked", "ODDS_BAND_HARD_BLOCK")

            if odds_band_survivability >= SAFE_SURVIVABILITY:
                risk_score -= 6
                risk_flags.append("SAFE_ODDS_BAND")
        else:
            if strong_exact_executable:
                risk_score += 5
                risk_flags.append("MISSING_ODDS_BAND_INTELLIGENCE_PENALTY")

        confidence_band_row = context.confidence_bands.get(
            (selected_market, selected_confidence_band)
        )

        if confidence_band_row:
            confidence_band_roi = _row_float(confidence_band_row, "recent_roi", "roi")
            confidence_band_survivability = _row_float(
                confidence_band_row,
                "survivability_score",
                "survivability",
            )

            if (
                confidence_band_roi <= HARD_BLOCK_ROI
                or confidence_band_survivability < HARD_BLOCK_SURVIVABILITY
            ):
                return _rejected(
                    "confidence-band hard blocked",
                    "CONFIDENCE_BAND_HARD_BLOCK",
                )

            if confidence_band_survivability >= SAFE_SURVIVABILITY:
                risk_score -= 6
                risk_flags.append("SAFE_CONFIDENCE_BAND")
        else:
            if strong_exact_executable:
                risk_score += 5
                risk_flags.append("MISSING_CONFIDENCE_BAND_INTELLIGENCE_PENALTY")

        tier_row = context.league_tiers.get(selected_league)

        if tier_row:
            tier = _row_str(tier_row, "tier", "priority_tier").upper()

            if tier == "VERY_STRONG":
                risk_score -= 12
            elif tier == "STRONG":
                risk_score -= 5
            elif tier == "WEAK":
                risk_score += 10

        family_row = context.market_families.get(selected_market_family)

        if family_row:
            family_roi = _row_float(family_row, "recent_roi", "roi")
            family_survivability = _row_float(
                family_row,
                "survivability_score",
                "survivability",
            )

            if family_roi > 0.10:
                risk_score -= 8
            elif family_roi < -0.10:
                risk_score += 8

            if family_survivability >= SAFE_SURVIVABILITY:
                risk_score -= 8

    risk_score = round(max(risk_score, 0.0), 2)
    tier = resolve_risk_tier(risk_score)

    if strict and tier == "AGGRESSIVE":
        return _rejected(
            "aggressive pick rejected in strict mode",
            "AGGRESSIVE_REJECTED",
        )

    return PortfolioFilterResult(
        allowed=tier != "REJECTED",
        reason=f"{tier.lower()} portfolio tier",
        risk_flags=sorted(set(risk_flags)),
        risk_score=risk_score,
        tier=tier,
    )