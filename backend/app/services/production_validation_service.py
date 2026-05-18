# backend/app/services/production_validation_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.odds.executable_market_registry import (
    parse_executable_market,
)


@dataclass(frozen=True)
class ProductionValidationResult:
    allowed: bool
    reason: str
    risk_flags: list[str]


def validate_prediction_for_production(
    *,
    market: str,
    predicted_label: str,
    odds_payload: dict[str, Any],
    odds: float | None,
    confidence: float,
    value_score: float | None,
    min_odds: float = 1.30,
    max_odds: float = 4.50,
    require_positive_value: bool = True,
) -> ProductionValidationResult:

    flags: list[str] = []

    executable = parse_executable_market(
        market
    )

    # =====================================================
    # ODDS REQUIRED
    # =====================================================

    if odds is None:
        return ProductionValidationResult(
            False,
            "missing_odds",
            ["missing_odds"],
        )

    # =====================================================
    # PRODUCTION READY
    # =====================================================

    if not executable.production_ready:
        return ProductionValidationResult(
            False,
            "market_not_production_ready",
            ["market_not_production_ready"],
        )

    # =====================================================
    # EXACT SCORE BLOCK
    # =====================================================

    if executable.family == "EXACT_SCORE":
        return ProductionValidationResult(
            False,
            "exact_score_blocked",
            ["exact_score_blocked"],
        )

    # =====================================================
    # HT/FT BLOCK
    # =====================================================

    if executable.family == "HT_FT":
        return ProductionValidationResult(
            False,
            "ht_ft_blocked",
            ["ht_ft_blocked"],
        )

    # =====================================================
    # EXTREME VOLATILITY
    # =====================================================

    if executable.volatility_tier == "EXTREME":
        return ProductionValidationResult(
            False,
            "extreme_market_volatility",
            ["extreme_market_volatility"],
        )

    # =====================================================
    # ODDS RANGE
    # =====================================================

    if odds < min_odds:
        return ProductionValidationResult(
            False,
            "odds_too_low",
            ["odds_too_low"],
        )

    if odds > max_odds:
        return ProductionValidationResult(
            False,
            "odds_too_high",
            ["odds_too_high"],
        )

    # =====================================================
    # CONFIDENCE
    # =====================================================

    if confidence <= 0 or confidence > 1:
        return ProductionValidationResult(
            False,
            "invalid_confidence",
            ["invalid_confidence"],
        )

    # =====================================================
    # BOOKMAKER
    # =====================================================

    if not odds_payload.get("odds_bookmaker"):
        return ProductionValidationResult(
            False,
            "missing_bookmaker",
            ["missing_bookmaker"],
        )

    # =====================================================
    # MARKET
    # =====================================================

    if not odds_payload.get("odds_market"):
        return ProductionValidationResult(
            False,
            "missing_odds_market",
            ["missing_odds_market"],
        )

    # =====================================================
    # SELECTION
    # =====================================================

    if not odds_payload.get("odds_selection"):
        return ProductionValidationResult(
            False,
            "missing_odds_selection",
            ["missing_odds_selection"],
        )

    # =====================================================
    # MATCH QUALITY
    # =====================================================

    if (
        odds_payload.get("odds_match_quality")
        != "exact_executable_market"
    ):
        return ProductionValidationResult(
            False,
            "non_exact_executable_match",
            ["non_exact_executable_match"],
        )

    odds_market = str(
        odds_payload["odds_market"]
    )

    odds_selection = str(
        odds_payload["odds_selection"]
    )

    # =====================================================
    # NON EXECUTABLE NOT
    # =====================================================

    if (
        predicted_label.startswith("NOT_")
        and "NOT_" in odds_selection
    ):
        return ProductionValidationResult(
            False,
            "non_executable_not_selection",
            ["non_executable_not_selection"],
        )

    # =====================================================
    # MARKET MISMATCH
    # =====================================================

    if (
        market != odds_market
        and not predicted_label.startswith("NOT_")
    ):
        return ProductionValidationResult(
            False,
            "market_odds_mismatch",
            ["market_odds_mismatch"],
        )

    # =====================================================
    # VALUE SCORE
    # =====================================================

    if value_score is None:
        flags.append(
            "missing_value_score"
        )

        if require_positive_value:
            return ProductionValidationResult(
                False,
                "missing_value_score",
                flags,
            )

    if (
        value_score is not None
        and value_score < 0
    ):
        flags.append(
            "negative_value_score"
        )

        if require_positive_value:
            return ProductionValidationResult(
                False,
                "negative_value_score",
                flags,
            )

    # =====================================================
    # EXECUTION RISK FLAGS
    # =====================================================

    if executable.execution_risk == "HIGH":
        flags.append(
            "high_execution_risk"
        )

    if executable.volatility_tier == "HIGH":
        flags.append(
            "high_volatility_market"
        )

    # =====================================================
    # FINAL
    # =====================================================

    return ProductionValidationResult(
        True,
        "production_validated",
        flags,
    )