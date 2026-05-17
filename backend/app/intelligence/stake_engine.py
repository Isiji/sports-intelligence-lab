# backend/app/intelligence/stake_engine.py

from __future__ import annotations

from dataclasses import dataclass
from math import prod


@dataclass(frozen=True)
class StakeDecision:
    stake: float
    method: str
    tier: str
    raw_kelly_fraction: float
    applied_fraction: float
    bankroll_pct: float
    total_odds: float
    estimated_probability: float
    expected_value: float
    reason: str


TIER_STAKE_MULTIPLIERS = {
    "SAFE": 1.00,
    "MODERATE": 0.50,
    "AGGRESSIVE": 0.25,
    "REJECTED": 0.00,
}


TIER_MAX_BANKROLL_PCT = {
    "SAFE": 0.02,
    "MODERATE": 0.01,
    "AGGRESSIVE": 0.005,
    "REJECTED": 0.00,
}


GLOBAL_MAX_BANKROLL_PCT = 0.02
DEFAULT_FRACTIONAL_KELLY = 0.25


def resolve_group_tier(
    average_risk_score: float,
    max_risk_score: float,
    rejected_picks: int = 0,
) -> str:
    if rejected_picks > 0:
        return "REJECTED"

    if max_risk_score >= 66 or average_risk_score >= 55:
        return "REJECTED"

    if max_risk_score >= 45 or average_risk_score >= 30:
        return "AGGRESSIVE"

    if max_risk_score >= 20 or average_risk_score >= 10:
        return "MODERATE"

    return "SAFE"


def calculate_group_stake(
    *,
    bankroll: float,
    odds_values: list[float],
    confidence_values: list[float],
    tier: str,
    flat_stake: float = 100.0,
    fractional_kelly: float = DEFAULT_FRACTIONAL_KELLY,
    max_bankroll_pct: float | None = None,
    min_stake: float = 0.0,
    daily_exposure_used: float = 0.0,
    daily_exposure_cap_pct: float = 0.15,
    group_exposure_cap_pct: float | None = None,
) -> StakeDecision:
    bankroll = float(bankroll or 0.0)

    if bankroll <= 0:
        return _blocked_decision(
            tier=tier,
            reason="No bankroll available.",
        )

    if tier == "REJECTED":
        return _blocked_decision(
            tier=tier,
            reason="Rejected risk tier.",
        )

    tier_max_pct = TIER_MAX_BANKROLL_PCT.get(tier, 0.0)

    effective_max_bankroll_pct = tier_max_pct

    if max_bankroll_pct is not None:
        effective_max_bankroll_pct = min(
            effective_max_bankroll_pct,
            float(max_bankroll_pct),
        )

    if group_exposure_cap_pct is not None:
        effective_max_bankroll_pct = min(
            effective_max_bankroll_pct,
            float(group_exposure_cap_pct),
        )

    effective_max_bankroll_pct = min(
        effective_max_bankroll_pct,
        GLOBAL_MAX_BANKROLL_PCT,
    )

    remaining_daily_exposure = max(
        bankroll * daily_exposure_cap_pct - daily_exposure_used,
        0.0,
    )

    if remaining_daily_exposure <= 0:
        return _blocked_decision(
            tier=tier,
            reason="Daily exposure cap reached.",
        )

    if effective_max_bankroll_pct <= 0:
        return _blocked_decision(
            tier=tier,
            reason="Tier bankroll cap is zero.",
        )

    if not odds_values or len(odds_values) != len(confidence_values):
        fallback_stake = min(
            flat_stake * TIER_STAKE_MULTIPLIERS.get(tier, 0.25),
            bankroll * effective_max_bankroll_pct,
            remaining_daily_exposure,
        )

        return StakeDecision(
            stake=round(max(fallback_stake, min_stake), 2),
            method="flat_fallback",
            tier=tier,
            raw_kelly_fraction=0.0,
            applied_fraction=round(effective_max_bankroll_pct, 6),
            bankroll_pct=round(fallback_stake / bankroll, 6),
            total_odds=0.0,
            estimated_probability=0.0,
            expected_value=0.0,
            reason="Missing complete odds/confidence data.",
        )

    clean_odds = [float(odds) for odds in odds_values if odds is not None]
    clean_confidences = [
        max(0.01, min(float(confidence), 0.99))
        for confidence in confidence_values
        if confidence is not None
    ]

    if len(clean_odds) != len(odds_values) or len(clean_confidences) != len(confidence_values):
        return _blocked_decision(
            tier=tier,
            reason="Invalid odds/confidence data.",
        )

    total_odds = prod(clean_odds)

    estimated_probability = prod(clean_confidences)

    if total_odds <= 1.0:
        return _blocked_decision(
            tier=tier,
            reason="Invalid group odds.",
        )

    expected_value = (total_odds * estimated_probability) - 1.0

    if expected_value <= 0:
        return _blocked_decision(
            tier=tier,
            reason="Negative or zero expected value.",
            total_odds=total_odds,
            estimated_probability=estimated_probability,
            expected_value=expected_value,
        )

    raw_kelly = expected_value / (total_odds - 1.0)
    raw_kelly = max(raw_kelly, 0.0)

    tier_multiplier = TIER_STAKE_MULTIPLIERS.get(tier, 0.25)

    applied_fraction = raw_kelly * fractional_kelly * tier_multiplier
    applied_fraction = min(applied_fraction, effective_max_bankroll_pct)

    stake = bankroll * applied_fraction

    if stake <= 0:
        stake = min(
            flat_stake * tier_multiplier,
            bankroll * effective_max_bankroll_pct,
            remaining_daily_exposure,
        )

    stake = min(
        stake,
        bankroll * effective_max_bankroll_pct,
        remaining_daily_exposure,
    )

    if stake < min_stake:
        return _blocked_decision(
            tier=tier,
            reason="Calculated stake below minimum stake.",
            total_odds=total_odds,
            estimated_probability=estimated_probability,
            expected_value=expected_value,
        )

    return StakeDecision(
        stake=round(stake, 2),
        method="fractional_kelly",
        tier=tier,
        raw_kelly_fraction=round(raw_kelly, 6),
        applied_fraction=round(applied_fraction, 6),
        bankroll_pct=round(stake / bankroll, 6),
        total_odds=round(total_odds, 6),
        estimated_probability=round(estimated_probability, 6),
        expected_value=round(expected_value, 6),
        reason="Dynamic stake calculated with tier, Kelly, and exposure caps.",
    )


def _blocked_decision(
    *,
    tier: str,
    reason: str,
    total_odds: float = 0.0,
    estimated_probability: float = 0.0,
    expected_value: float = 0.0,
) -> StakeDecision:
    return StakeDecision(
        stake=0.0,
        method="blocked",
        tier=tier,
        raw_kelly_fraction=0.0,
        applied_fraction=0.0,
        bankroll_pct=0.0,
        total_odds=round(total_odds, 6),
        estimated_probability=round(estimated_probability, 6),
        expected_value=round(expected_value, 6),
        reason=reason,
    )