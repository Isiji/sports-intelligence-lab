# backend/app/intelligence/odds_economics.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OddsEconomicsResult:
    allowed: bool
    tier: str
    penalty: float
    reasons: list[str]


def evaluate_odds_economics(
    *,
    odds: float | None,
    confidence: float | None,
    value_score: float | None,
    production_mode: bool = True,
) -> OddsEconomicsResult:
    reasons: list[str] = []
    penalty = 0.0

    if odds is None:
        return OddsEconomicsResult(False, "NO_ODDS", 100.0, ["missing odds"])

    odds = float(odds)
    confidence = float(confidence or 0.0)
    value_score = float(value_score or 0.0)

    if odds <= 1.01:
        return OddsEconomicsResult(False, "INVALID", 100.0, ["invalid odds"])

    if odds < 1.15:
        return OddsEconomicsResult(
            False,
            "UNPROFITABLE_LOW_ODDS",
            90.0,
            ["odds too low for long-term profitability"],
        )

    if production_mode and odds < 1.25:
        return OddsEconomicsResult(
            False,
            "LOW_PAYOUT_BLOCKED",
            70.0,
            ["low payout blocked in production mode"],
        )

    if odds < 1.35:
        penalty += 25.0
        reasons.append("low payout odds")

    if value_score < 0:
        penalty += 30.0
        reasons.append("negative value score")

    if confidence >= 0.90 and odds < 1.40:
        penalty += 25.0
        reasons.append("overconfident low-payout pick")

    if odds > 4.50:
        penalty += 25.0
        reasons.append("high variance odds")

    if penalty >= 60:
        return OddsEconomicsResult(False, "BAD_ECONOMICS", penalty, reasons)

    if penalty >= 30:
        return OddsEconomicsResult(True, "WATCHLIST", penalty, reasons)

    return OddsEconomicsResult(True, "HEALTHY", penalty, reasons)