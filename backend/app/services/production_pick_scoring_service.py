# backend/app/services/production_pick_scoring_service.py

from __future__ import annotations

from typing import Any

from app.intelligence.odds_economics import evaluate_odds_economics


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

    score = 0.0
    reasons: list[str] = []

    economics = evaluate_odds_economics(
        odds=odds,
        confidence=confidence,
        value_score=value_score,
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

    score += confidence * 45.0

    if confidence >= 0.85:
        score += 8.0
        reasons.append("strong confidence")
    elif confidence >= 0.70:
        score += 5.0
        reasons.append("acceptable confidence")
    else:
        score -= 10.0
        reasons.append("low confidence")

    if value_score > 0:
        score += min(value_score * 120.0, 30.0)
        reasons.append("positive value edge")
    else:
        score -= 20.0
        reasons.append("no confirmed value edge")

    selected_odds = _safe_float(odds)

    if 1.35 <= selected_odds <= 2.80:
        score += 15.0
        reasons.append("healthy production odds")
    elif 2.80 < selected_odds <= 4.50:
        score += 5.0
        reasons.append("higher payout but more variance")
    else:
        score -= 15.0
        reasons.append("weak odds economics")

    score -= economics.penalty

    reasons.extend(economics.reasons)

    score = round(max(score, 0.0), 4)

    if score >= 85:
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
    }


def score_pick_list(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = [score_production_pick(row) for row in rows]

    return sorted(
        scored,
        key=lambda item: (
            item["production_score"],
            _safe_float(item.get("value_score")),
            _safe_float(item.get("confidence")),
        ),
        reverse=True,
    )