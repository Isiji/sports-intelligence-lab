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
    fractional_kelly: float = 0.25,
    max_bankroll_pct: float | None = None,
    min_stake: float = 0.0,
) -> StakeDecision:
    if bankroll <= 0:
        return StakeDecision(
            0.0,
            "blocked",
            tier,
            0.0,
            0.0,
            "No bankroll available.",
        )

    if tier == "REJECTED":
        return StakeDecision(
            0.0,
            "blocked",
            tier,
            0.0,
            0.0,
            "Rejected risk tier.",
        )

    tier_max_bankroll_pct = TIER_MAX_BANKROLL_PCT.get(tier, 0.0)

    effective_max_bankroll_pct = (
        tier_max_bankroll_pct
        if max_bankroll_pct is None
        else min(max_bankroll_pct, tier_max_bankroll_pct)
    )

    if effective_max_bankroll_pct <= 0:
        return StakeDecision(
            0.0,
            "blocked",
            tier,
            0.0,
            0.0,
            "Tier has zero bankroll allocation.",
        )

    if not odds_values or len(odds_values) != len(confidence_values):
        stake = min(
            flat_stake * TIER_STAKE_MULTIPLIERS.get(tier, 0.25),
            bankroll * effective_max_bankroll_pct,
        )

        return StakeDecision(
            stake=round(max(stake, min_stake), 2),
            method="flat_fallback",
            tier=tier,
            raw_kelly_fraction=0.0,
            applied_fraction=round(effective_max_bankroll_pct, 6),
            reason="Missing complete odds/confidence data.",
        )

    total_odds = prod(odds_values)

    estimated_probability = prod(
        max(0.01, min(float(confidence), 0.99))
        for confidence in confidence_values
    )

    if total_odds <= 1.0:
        return StakeDecision(
            0.0,
            "blocked",
            tier,
            0.0,
            0.0,
            "Invalid group odds.",
        )

    raw_kelly = ((total_odds * estimated_probability) - 1.0) / (total_odds - 1.0)
    raw_kelly = max(raw_kelly, 0.0)

    tier_multiplier = TIER_STAKE_MULTIPLIERS.get(tier, 0.25)

    applied_fraction = raw_kelly * fractional_kelly * tier_multiplier
    applied_fraction = min(applied_fraction, effective_max_bankroll_pct)

    stake = bankroll * applied_fraction

    if stake <= 0:
        stake = min(
            flat_stake * tier_multiplier,
            bankroll * effective_max_bankroll_pct,
        )

    return StakeDecision(
        stake=round(max(stake, min_stake), 2),
        method="fractional_kelly",
        tier=tier,
        raw_kelly_fraction=round(raw_kelly, 6),
        applied_fraction=round(applied_fraction, 6),
        reason=(
            "Dynamic stake calculated with fractional Kelly, "
            "tier multiplier, and tier bankroll cap."
        ),
    )