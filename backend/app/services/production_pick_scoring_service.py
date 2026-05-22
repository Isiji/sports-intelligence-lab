# backend/app/services/production_pick_scoring_service.py

from __future__ import annotations

from typing import Any

from app.intelligence.odds_economics import evaluate_odds_economics
from app.odds.executable_market_registry import parse_executable_market
from app.services.market_alternatives_engine import (
    resolve_market_alternatives,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score_production_pick(
    row: dict[str, Any]
) -> dict[str, Any]:

    confidence = _safe_float(
        row.get("confidence")
    )

    value_score = _safe_float(
        row.get("value_score")
    )

    odds = row.get("odds")

    market = str(
        row.get("market") or ""
    )

    score = 0.0

    reasons: list[str] = []

    executable = parse_executable_market(
        market
    )

    economics = evaluate_odds_economics(
        odds=odds,
        confidence=confidence,
        value_score=value_score,
        market=market,
        production_mode=True,
    )

    survivability_score = _safe_float(
        row.get(
            "survivability_score"
        )
    )

    freshness_score = _safe_float(
        row.get(
            "freshness_score"
        )
    )

    persistence_score = _safe_float(
        row.get(
            "persistence_score"
        )
    )

    downgrade_risk_score = _safe_float(
        row.get(
            "downgrade_risk_score"
        )
    )

    stale_odds = bool(
        row.get("stale_odds")
    )

    execution_ready = bool(
        row.get("execution_ready")
    )

    survivability_bucket = str(
        row.get(
            "survivability_bucket"
        ) or ""
    )

    alternatives = resolve_market_alternatives(
        market
    )

    if not economics.allowed:
        return {
            **row,
            "production_score": 0.0,
            "pick_grade": "D",
            "risk_level": "AVOID",
            "selection_reasons": economics.reasons,
            "odds_economics_tier": economics.tier,
            "market_alternatives": alternatives,
            "survivability_score": survivability_score,
            "freshness_score": freshness_score,
            "persistence_score": persistence_score,
            "downgrade_risk_score": downgrade_risk_score,
            "stale_odds": stale_odds,
            "execution_ready": execution_ready,
            "survivability_bucket": survivability_bucket,
        }

    score += confidence * 48.0

    if confidence >= 0.82:
        score += 12.0
        reasons.append(
            "strong confidence"
        )

    elif confidence >= 0.70:
        score += 8.0
        reasons.append(
            "good confidence"
        )

    elif confidence >= 0.60:
        score += 3.0
        reasons.append(
            "acceptable confidence"
        )

    else:
        score -= 12.0
        reasons.append(
            "low confidence"
        )

    if value_score >= 0.25:
        score += 28.0
        reasons.append(
            "elite value edge"
        )

    elif value_score >= 0.15:
        score += 22.0
        reasons.append(
            "strong value edge"
        )

    elif value_score >= 0.08:
        score += 15.0
        reasons.append(
            "good value edge"
        )

    elif value_score >= 0.03:
        score += 8.0
        reasons.append(
            "positive value edge"
        )

    else:
        score -= 18.0
        reasons.append(
            "weak value edge"
        )

    selected_odds = _safe_float(odds)

    if 1.35 <= selected_odds <= 2.20:
        score += 18.0
        reasons.append(
            "healthy production odds"
        )

    elif 2.20 < selected_odds <= 3.00:
        score += 10.0
        reasons.append(
            "acceptable value odds"
        )

    elif 3.00 < selected_odds <= 4.20:
        score += 2.0
        reasons.append(
            "higher variance odds"
        )

    else:
        score -= 18.0
        reasons.append(
            "weak odds economics"
        )

    if row.get("odds_match_quality") == "exact_executable_market":
        score += 12.0
        reasons.append(
            "exact executable odds match"
        )

    else:
        score -= 30.0
        reasons.append(
            "non-exact executable odds"
        )

    if row.get("odds_bookmaker"):
        score += 6.0
        reasons.append(
            "bookmaker traced"
        )

    else:
        score -= 20.0
        reasons.append(
            "missing bookmaker"
        )

    if executable.family in {
        "ASIAN_HANDICAP",
        "DOUBLE_CHANCE",
        "MATCH_RESULT",
        "GOALS_TOTAL",
        "BTTS",
        "FIRST_HALF_GOALS_TOTAL",
        "SECOND_HALF_GOALS_TOTAL",
        "FIRST_HALF_RESULT",
        "SECOND_HALF_RESULT",
    }:
        score += 6.0
        reasons.append(
            "production-supported market family"
        )

    if executable.family == "ASIAN_HANDICAP":

        if selected_odds >= 3.20:
            score -= 24.0
            reasons.append(
                "unstable handicap pricing"
            )

        else:
            score -= 6.0

    if executable.execution_risk == "MEDIUM":
        score -= 4.0
        reasons.append(
            "medium execution risk"
        )

    elif executable.execution_risk == "HIGH":
        score -= 25.0
        reasons.append(
            "high execution risk"
        )

    if executable.volatility_tier == "HIGH":
        score -= 8.0
        reasons.append(
            "high volatility"
        )

    elif executable.volatility_tier == "EXTREME":
        score -= 35.0
        reasons.append(
            "extreme volatility"
        )

    portfolio_risk_score = _safe_float(
        row.get(
            "portfolio_risk_score"
        )
    )

    if portfolio_risk_score <= 12:
        score += 8.0
        reasons.append(
            "low portfolio risk"
        )

    elif portfolio_risk_score <= 28:
        score += 3.0
        reasons.append(
            "acceptable portfolio risk"
        )

    else:
        score -= 18.0
        reasons.append(
            "elevated portfolio risk"
        )

    score += (
        survivability_score * 18.0
    )

    score += (
        freshness_score * 10.0
    )

    score += (
        persistence_score * 8.0
    )

    score -= (
        downgrade_risk_score * 16.0
    )

    if stale_odds:
        score -= 18.0
        reasons.append(
            "stale bookmaker odds"
        )

    if not execution_ready:
        score -= 22.0
        reasons.append(
            "not execution ready"
        )

    else:
        score += 6.0
        reasons.append(
            "execution ready"
        )

    if survivability_score < 0.40:
        score -= 22.0
        reasons.append(
            "low survivability"
        )

    elif survivability_score < 0.55:
        score -= 8.0
        reasons.append(
            "moderate survivability risk"
        )

    else:
        score += 6.0
        reasons.append(
            "strong survivability"
        )

    if survivability_bucket == "WEAK":
        score -= 15.0

    elif survivability_bucket == "MODERATE":
        score -= 4.0

    elif survivability_bucket == "ELITE":
        score += 8.0

    score -= economics.penalty * 0.45

    reasons.extend(
        economics.reasons
    )

    score = round(
        max(score, 0.0),
        4,
    )

    if score >= 86:
        grade = "A"
        risk_level = "LOW"

    elif score >= 70:
        grade = "B"
        risk_level = "MODERATE"

    elif score >= 55:
        grade = "C"
        risk_level = "HIGH"

    else:
        grade = "D"
        risk_level = "AVOID"

    return {
        **row,
        "production_score": score,
        "pick_grade": grade,
        "risk_level": risk_level,
        "selection_reasons": reasons,
        "odds_economics_tier": economics.tier,
        "market_alternatives": alternatives,
        "survivability_score": survivability_score,
        "freshness_score": freshness_score,
        "persistence_score": persistence_score,
        "downgrade_risk_score": downgrade_risk_score,
        "stale_odds": stale_odds,
        "execution_ready": execution_ready,
        "survivability_bucket": survivability_bucket,
    }

def score_pick_list(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = [score_production_pick(row) for row in rows]

    return sorted(
        scored,
        key=lambda item: (
            item["production_score"],
            _safe_float(item.get("value_score")),
            _safe_float(item.get("confidence")),
            -_safe_float(item.get("portfolio_risk_score"), 999.0),
        ),
        reverse=True,
    )