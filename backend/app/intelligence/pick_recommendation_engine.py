# backend/app/intelligence/pick_recommendation_engine.py

from __future__ import annotations

from typing import Any


def classify_pick_recommendation(
    pick: dict[str, Any],
) -> dict[str, Any]:
    production_score = float(
        pick.get("production_score") or 0.0
    )

    risk_level = pick.get("risk_level") or "UNKNOWN"
    odds = pick.get("odds")
    value_score = pick.get("value_score")
    exposure_rejected = bool(
        pick.get("exposure_rejected") or False
    )

    reasons: list[str] = []

    if exposure_rejected:
        reasons.append("Rejected by exposure control")

    if odds is None:
        reasons.append("Missing odds")

    if value_score is None:
        reasons.append("Missing value score")

    if risk_level == "AVOID":
        reasons.append("Risk level is AVOID")

    if production_score >= 80 and not exposure_rejected:
        status = "APPROVED"
    elif production_score >= 55 and not exposure_rejected:
        status = "WATCHLIST"
    else:
        status = "REJECTED"

    if odds is None or value_score is None:
        if status == "APPROVED":
            status = "WATCHLIST"
        elif status == "WATCHLIST":
            status = "REJECTED"

    if risk_level == "AVOID":
        status = "REJECTED"

    if exposure_rejected:
        status = "REJECTED"

    return {
        **pick,
        "recommendation_status": status,
        "recommendation_reasons": reasons,
    }


def build_recommendation_layer(
    exposure_result: dict[str, Any],
) -> dict[str, Any]:
    accepted_source = exposure_result.get(
        "accepted_picks",
        [],
    )

    rejected_source = exposure_result.get(
        "rejected_picks",
        [],
    )

    accepted_classified = [
        classify_pick_recommendation(pick)
        for pick in accepted_source
    ]

    rejected_classified = [
        classify_pick_recommendation(pick)
        for pick in rejected_source
    ]

    all_picks = accepted_classified + rejected_classified

    approved_picks = [
        pick
        for pick in all_picks
        if pick["recommendation_status"] == "APPROVED"
    ]

    watchlist_picks = [
        pick
        for pick in all_picks
        if pick["recommendation_status"] == "WATCHLIST"
    ]

    rejected_picks = [
        pick
        for pick in all_picks
        if pick["recommendation_status"] == "REJECTED"
    ]

    return {
        "approved_picks": approved_picks,
        "watchlist_picks": watchlist_picks,
        "rejected_picks": rejected_picks,
        "recommendation_summary": {
            "approved": len(approved_picks),
            "watchlist": len(watchlist_picks),
            "rejected": len(rejected_picks),
            "total": len(all_picks),
        },
    }