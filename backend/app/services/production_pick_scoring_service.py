# backend/app/services/production_pick_scoring_service.py

from __future__ import annotations

from typing import Any

from app.intelligence.odds_economics import evaluate_odds_economics
from app.odds.executable_market_registry import parse_executable_market


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score_production_pick(row: dict[str, Any]) -> dict[str, Any]:
    confidence = _safe_float(row.get("confidence"))
    value_score = _safe_float(row.get("value_score"))
    odds = row.get("odds")
    market = str(row.get("market") or "")

    score = 0.0
    reasons: list[str] = []

    executable = parse_executable_market(market)

    economics = evaluate_odds_economics(
        odds=odds,
        confidence=confidence,
        value_score=value_score,
        market=market,
        production_mode=True,
    )

    if not economics.allowed:
        return {
            **row,
            "production_score": 0.0,
            "pick_grade": "D",
            "risk_level": "AVOID",
            "selection_reasons": economics.reasons,
            "odds_economics_tier": economics.tier,
        }

    # Confidence
    score += confidence * 48.0

    if confidence >= 0.82:
        score += 12.0
        reasons.append("strong confidence")
    elif confidence >= 0.70:
        score += 8.0
        reasons.append("good confidence")
    elif confidence >= 0.60:
        score += 3.0
        reasons.append("acceptable confidence")
    else:
        score -= 12.0
        reasons.append("low confidence")

    # Value edge
    if value_score >= 0.25:
        score += 28.0
        reasons.append("elite value edge")
    elif value_score >= 0.15:
        score += 22.0
        reasons.append("strong value edge")
    elif value_score >= 0.08:
        score += 15.0
        reasons.append("good value edge")
    elif value_score >= 0.03:
        score += 8.0
        reasons.append("positive value edge")
    else:
        score -= 18.0
        reasons.append("weak value edge")

    selected_odds = _safe_float(odds)

    if 1.35 <= selected_odds <= 2.20:
        score += 18.0
        reasons.append("healthy production odds")
    elif 2.20 < selected_odds <= 3.00:
        score += 10.0
        reasons.append("acceptable value odds")
    elif 3.00 < selected_odds <= 4.20:
        score += 2.0
        reasons.append("higher variance odds")
    else:
        score -= 18.0
        reasons.append("weak odds economics")

    # Exact execution
    if row.get("odds_match_quality") == "exact_executable_market":
        score += 12.0
        reasons.append("exact executable odds match")
    else:
        score -= 30.0
        reasons.append("non-exact executable odds")

    if row.get("odds_bookmaker"):
        score += 6.0
        reasons.append("bookmaker traced")
    else:
        score -= 20.0
        reasons.append("missing bookmaker")

    # Market-family bonuses/penalties
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
        reasons.append("production-supported market family")

    if executable.execution_risk == "MEDIUM":
        score -= 4.0
        reasons.append("medium execution risk")
    elif executable.execution_risk == "HIGH":
        score -= 25.0
        reasons.append("high execution risk")

    if executable.volatility_tier == "HIGH":
        score -= 8.0
        reasons.append("high volatility")
    elif executable.volatility_tier == "EXTREME":
        score -= 35.0
        reasons.append("extreme volatility")

    portfolio_risk_score = _safe_float(row.get("portfolio_risk_score"))
    if portfolio_risk_score <= 12:
        score += 8.0
        reasons.append("low portfolio risk")
    elif portfolio_risk_score <= 28:
        score += 3.0
        reasons.append("acceptable portfolio risk")
    else:
        score -= 18.0
        reasons.append("elevated portfolio risk")

    # Keep economics penalty, but softer because upstream already filtered.
    score -= economics.penalty * 0.45
    reasons.extend(economics.reasons)

    score = round(max(score, 0.0), 4)

    if score >= 82:
        grade = "A"
        risk_level = "LOW"
    elif score >= 66:
        grade = "B"
        risk_level = "MODERATE"
    elif score >= 52:
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