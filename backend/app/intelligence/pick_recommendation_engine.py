# backend/app/intelligence/pick_recommendation_engine.py

from __future__ import annotations

from typing import Any

from app.services.market_alternatives_engine import (
    resolve_market_alternatives,
)


def classify_pick_recommendation(
    pick: dict[str, Any],
) -> dict[str, Any]:

    production_score = float(
        pick.get("production_score") or 0.0
    )

    risk_level = str(
        pick.get("risk_level") or "UNKNOWN"
    )

    odds = pick.get("odds")
    value_score = pick.get("value_score")

    exposure_rejected = bool(
        pick.get("exposure_rejected") or False
    )

    survivability_score = float(
        pick.get("survivability_score") or 0.0
    )

    freshness_score = float(
        pick.get("freshness_score") or 0.0
    )

    downgrade_risk_score = float(
        pick.get("downgrade_risk_score") or 0.0
    )

    stale_odds = bool(
        pick.get("stale_odds")
    )

    execution_ready = bool(
        pick.get("execution_ready")
    )

    survivability_bucket = str(
        pick.get("survivability_bucket") or ""
    )

    alternatives = resolve_market_alternatives(
        str(pick.get("market") or "")
    )

    reasons: list[str] = []

    if exposure_rejected:
        reasons.append(
            "Rejected by exposure control"
        )

    if odds is None:
        reasons.append(
            "Missing odds"
        )

    if value_score is None:
        reasons.append(
            "Missing value score"
        )

    if risk_level == "AVOID":
        reasons.append(
            "Risk level is AVOID"
        )

    if stale_odds:
        reasons.append(
            "Stale bookmaker odds"
        )

    if not execution_ready:
        reasons.append(
            "Not execution ready"
        )

    if survivability_score < 0.45:
        reasons.append(
            "Low market survivability"
        )

    if freshness_score < 0.45:
        reasons.append(
            "Weak odds freshness"
        )

    if downgrade_risk_score > 0.70:
        reasons.append(
            "High downgrade risk"
        )

    if production_score >= 86 and not exposure_rejected:
        status = "APPROVED"

    elif production_score >= 60 and not exposure_rejected:
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

    if stale_odds:
        if status == "APPROVED":
            status = "WATCHLIST"
        elif status == "WATCHLIST":
            status = "REJECTED"

    if not execution_ready:
        if status == "APPROVED":
            status = "WATCHLIST"
        elif status == "WATCHLIST":
            status = "REJECTED"

    if survivability_score < 0.40:
        status = "REJECTED"

    elif survivability_score < 0.55:
        if status == "APPROVED":
            status = "WATCHLIST"

    if survivability_bucket == "WEAK":
        status = "REJECTED"

    if downgrade_risk_score > 0.75:
        status = "REJECTED"

    return {
        **pick,
        "recommendation_status": status,
        "recommendation_reasons": reasons,
        "market_alternatives": alternatives,
        "survivability_score": survivability_score,
        "freshness_score": freshness_score,
        "downgrade_risk_score": downgrade_risk_score,
        "stale_odds": stale_odds,
        "execution_ready": execution_ready,
        "survivability_bucket": survivability_bucket,
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

    all_picks = (
        accepted_classified
        + rejected_classified
    )

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