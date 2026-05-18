# backend/app/intelligence/odds_economics.py

from __future__ import annotations

from dataclasses import dataclass

from app.odds.executable_market_registry import (
    parse_executable_market,
)


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
    market: str | None = None,
    production_mode: bool = True,
) -> OddsEconomicsResult:

    reasons: list[str] = []

    penalty = 0.0

    if odds is None:
        return OddsEconomicsResult(
            False,
            "NO_ODDS",
            100.0,
            ["missing odds"],
        )

    odds = float(odds)

    confidence = float(
        confidence or 0.0
    )

    value_score = float(
        value_score or 0.0
    )

    executable = None

    if market:
        executable = parse_executable_market(
            market
        )

    # =====================================================
    # BASIC VALIDATION
    # =====================================================

    if odds <= 1.01:
        return OddsEconomicsResult(
            False,
            "INVALID",
            100.0,
            ["invalid odds"],
        )

    # =====================================================
    # PRODUCTION LOW ODDS
    # =====================================================

    if odds < 1.15:
        return OddsEconomicsResult(
            False,
            "UNPROFITABLE_LOW_ODDS",
            90.0,
            ["odds too low for long-term profitability"],
        )

    if (
        production_mode
        and odds < 1.25
    ):
        return OddsEconomicsResult(
            False,
            "LOW_PAYOUT_BLOCKED",
            70.0,
            ["low payout blocked in production mode"],
        )

    # =====================================================
    # LOW ODDS PENALTY
    # =====================================================

    if odds < 1.35:
        penalty += 25.0
        reasons.append(
            "low payout odds"
        )

    # =====================================================
    # NEGATIVE VALUE
    # =====================================================

    if value_score < 0:
        penalty += 30.0
        reasons.append(
            "negative value score"
        )

    # =====================================================
    # OVERCONFIDENCE
    # =====================================================

    if (
        confidence >= 0.90
        and odds < 1.40
    ):
        penalty += 25.0

        reasons.append(
            "overconfident low-payout pick"
        )

    # =====================================================
    # HIGH VARIANCE ODDS
    # =====================================================

    if odds > 4.50:
        penalty += 25.0

        reasons.append(
            "high variance odds"
        )

    # =====================================================
    # EXECUTABLE MARKET RISK
    # =====================================================

    if executable:

        if executable.execution_risk == "HIGH":
            penalty += 35.0

            reasons.append(
                "high execution risk"
            )

        elif executable.execution_risk == "MEDIUM":
            penalty += 12.0

            reasons.append(
                "medium execution risk"
            )

        # =================================================
        # VOLATILITY
        # =================================================

        if executable.volatility_tier == "EXTREME":
            penalty += 35.0

            reasons.append(
                "extreme volatility market"
            )

        elif executable.volatility_tier == "HIGH":
            penalty += 18.0

            reasons.append(
                "high volatility market"
            )

        # =================================================
        # EXACT SCORE
        # =================================================

        if executable.family == "EXACT_SCORE":

            if production_mode:
                return OddsEconomicsResult(
                    False,
                    "EXACT_SCORE_BLOCKED",
                    100.0,
                    ["exact score blocked in production"],
                )

        # =================================================
        # HT/FT
        # =================================================

        if executable.family == "HT_FT":

            if production_mode:
                return OddsEconomicsResult(
                    False,
                    "HTFT_BLOCKED",
                    100.0,
                    ["ht_ft blocked in production"],
                )

        # =================================================
        # EXTREME ODDS CONTROL
        # =================================================

        if (
            executable.family in {
                "EXACT_SCORE",
                "HT_FT",
            }
            and odds > 8.0
        ):
            return OddsEconomicsResult(
                False,
                "EXTREME_DERIVATIVE_RISK",
                100.0,
                ["extreme derivative odds"],
            )

    # =====================================================
    # FINAL
    # =====================================================

    if penalty >= 60:
        return OddsEconomicsResult(
            False,
            "BAD_ECONOMICS",
            penalty,
            reasons,
        )

    if penalty >= 30:
        return OddsEconomicsResult(
            True,
            "WATCHLIST",
            penalty,
            reasons,
        )

    return OddsEconomicsResult(
        True,
        "HEALTHY",
        penalty,
        reasons,
    )