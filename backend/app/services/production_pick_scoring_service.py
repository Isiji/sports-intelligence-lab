# backend/app/services/production_pick_scoring_service.py

from __future__ import annotations

from typing import Any


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
    odds = _safe_float(row.get("odds"))

    score = 0.0
    reasons: list[str] = []

    score += confidence * 60.0

    if confidence >= 0.85:
        score += 15.0
        reasons.append("elite confidence")
    elif confidence >= 0.75:
        score += 10.0
        reasons.append("strong confidence")
    elif confidence >= 0.65:
        score += 5.0
        reasons.append("acceptable confidence")
    else:
        score -= 10.0
        reasons.append("low confidence")

    if value_score > 0:
        value_points = min(value_score * 100.0, 25.0)
        score += value_points
        reasons.append("positive value edge")
    else:
        score -= 5.0
        reasons.append("no confirmed value edge")

    if odds > 0:
        score += 10.0
        reasons.append("odds-backed pick")

        if 1.30 <= odds <= 2.50:
            score += 5.0
            reasons.append("healthy odds range")
        elif odds > 3.50:
            score -= 5.0
            reasons.append("high-variance odds")
    else:
        score -= 15.0
        reasons.append("missing odds")

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