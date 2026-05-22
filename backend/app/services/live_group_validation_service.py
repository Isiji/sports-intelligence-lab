# backend/app/services/live_group_validation_service.py

from __future__ import annotations

from typing import Any


MIN_SURVIVABILITY = 0.40
MAX_DOWNGRADE_RISK = 0.70


def validate_group_for_execution(
    group: list[dict[str, Any]],
) -> dict[str, Any]:

    approved: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    total_survivability = 0.0

    for item in group:

        survivability = float(
            item.get(
                "survivability_score"
            ) or 0.0
        )

        downgrade_risk = float(
            item.get(
                "downgrade_risk_score"
            ) or 0.0
        )

        stale_odds = bool(
            item.get("stale_odds")
        )

        if stale_odds:
            rejected.append(
                {
                    **item,
                    "validation_reason": "stale_odds",
                }
            )
            continue

        if survivability < MIN_SURVIVABILITY:
            rejected.append(
                {
                    **item,
                    "validation_reason": "low_survivability",
                }
            )
            continue

        if downgrade_risk > MAX_DOWNGRADE_RISK:
            rejected.append(
                {
                    **item,
                    "validation_reason": "high_downgrade_risk",
                }
            )
            continue

        approved.append(item)

        total_survivability += survivability

    average_survivability = 0.0

    if approved:
        average_survivability = (
            total_survivability
            / len(approved)
        )

    allowed = len(approved) >= 2

    return {
        "allowed": allowed,
        "approved_picks": approved,
        "rejected_picks": rejected,
        "average_survivability": round(
            average_survivability,
            4,
        ),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
    }