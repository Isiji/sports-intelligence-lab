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


RELAXED_EXECUTION_QUALITIES = {
    "exact_executable_market",
    "exact_canonical",
    "direct",
    "asian_handicap_family_fallback",
    "execution_family_fallback",
}


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

    executable_market = (
        odds_payload.get("execution_market")
        or odds_payload.get("executable_market")
        or market
    )

    executable = parse_executable_market(
        executable_market
    )

    if odds is None:
        return ProductionValidationResult(False, "missing_odds", ["missing_odds"])

    if not executable.production_ready:
        return ProductionValidationResult(False, "market_not_production_ready", ["market_not_production_ready"])

    if executable.family in {"EXACT_SCORE", "HT_FT"}:
        return ProductionValidationResult(False, "derivative_market_blocked", ["derivative_market_blocked"])

    if executable.volatility_tier == "EXTREME":
        return ProductionValidationResult(False, "extreme_market_volatility", ["extreme_market_volatility"])

    if executable.family == "RESULT_TOTAL":
        max_odds = min(max_odds, 4.50)
        min_confidence = 0.62
        min_value = 0.035
    elif executable.family == "HANDICAP_RESULT":
        max_odds = min(max_odds, 4.00)
        min_confidence = 0.60
        min_value = 0.03
    else:
        min_confidence = 0.0
        min_value = 0.0

    if odds < min_odds:
        return ProductionValidationResult(False, "odds_too_low", ["odds_too_low"])

    if odds > max_odds:
        return ProductionValidationResult(False, "odds_too_high", ["odds_too_high"])

    if confidence <= 0 or confidence > 1:
        return ProductionValidationResult(False, "invalid_confidence", ["invalid_confidence"])

    if confidence < min_confidence:
        return ProductionValidationResult(False, "confidence_too_low_for_market", ["confidence_too_low_for_market"])

    if not odds_payload.get("odds_bookmaker"):
        return ProductionValidationResult(False, "missing_bookmaker", ["missing_bookmaker"])

    if not odds_payload.get("odds_market"):
        return ProductionValidationResult(False, "missing_odds_market", ["missing_odds_market"])

    if not odds_payload.get("odds_selection"):
        return ProductionValidationResult(False, "missing_odds_selection", ["missing_odds_selection"])

    match_quality = odds_payload.get("odds_match_quality")

    if match_quality not in RELAXED_EXECUTION_QUALITIES:
        return ProductionValidationResult(False, "weak_odds_match_quality", ["weak_odds_match_quality"])

    odds_selection = str(odds_payload["odds_selection"])

    if predicted_label.startswith("NOT_") and "NOT_" in odds_selection:
        return ProductionValidationResult(False, "non_executable_not_selection", ["non_executable_not_selection"])

    execution_score = odds_payload.get("execution_score")
    local_realism_score = odds_payload.get("local_realism_score")

    if execution_score is not None and float(execution_score) < 55.0:
        return ProductionValidationResult(False, "execution_score_too_low", ["execution_score_too_low"])

    if local_realism_score is not None and float(local_realism_score) < 0.20:
        flags.append("low_local_realism")

    if value_score is None:
        flags.append("missing_value_score")

        if require_positive_value:
            return ProductionValidationResult(False, "missing_value_score", flags)

    if value_score is not None and value_score < 0:
        flags.append("negative_value_score")

        if require_positive_value:
            return ProductionValidationResult(False, "negative_value_score", flags)

    if value_score is not None and value_score < min_value:
        return ProductionValidationResult(False, "value_score_too_low_for_market", ["value_score_too_low_for_market"])

    if executable.execution_risk == "HIGH":
        flags.append("high_execution_risk")

    if executable.volatility_tier == "HIGH":
        flags.append("high_volatility_market")

    if executable.family in {"RESULT_TOTAL", "HANDICAP_RESULT"}:
        flags.append("controlled_derivative_market")

    return ProductionValidationResult(True, "production_validated", flags)