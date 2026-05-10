from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ConfidenceBandIntelligenceSnapshot


MARKET_CONFIDENCE_CAPS = {
    "draw": 0.82,
    "home_win": 0.88,
    "away_win": 0.86,

    "double_chance_1x": 0.94,
    "double_chance_x2": 0.94,
    "double_chance_12": 0.92,

    "over_1_5_goals": 0.92,
    "under_1_5_goals": 0.86,
    "over_2_5_goals": 0.88,
    "under_2_5_goals": 0.90,
    "over_3_5_goals": 0.84,
    "under_3_5_goals": 0.93,

    "btts_yes": 0.90,
    "btts_no": 0.90,

    "corners_over": 0.78,
    "corners_under": 0.78,
    "shots_on_target_over": 0.72,
    "shots_on_target_under": 0.72,
}


def resolve_confidence_band(confidence: float) -> str:
    if confidence < 0.60:
        return "0.00-0.59"

    if confidence < 0.70:
        return "0.60-0.69"

    if confidence < 0.80:
        return "0.70-0.79"

    if confidence < 0.90:
        return "0.80-0.89"

    return "0.90+"


def recalibrate_confidence(
    *,
    session: Session,
    market: str,
    confidence: float,
    min_sample_size: int = 20,
) -> dict:
    original_confidence = max(
        min(float(confidence or 0.0), 0.99),
        0.01,
    )

    confidence_band = resolve_confidence_band(original_confidence)

    adjusted_confidence = original_confidence
    reasons: list[str] = []

    row = (
        session.query(ConfidenceBandIntelligenceSnapshot)
        .filter(
            ConfidenceBandIntelligenceSnapshot.market == market,
            ConfidenceBandIntelligenceSnapshot.confidence_band == confidence_band,
        )
        .first()
    )

    if row:
        sample_size = int(getattr(row, "sample_size", 0) or 0)
        hit_rate = float(getattr(row, "hit_rate", 0.0) or 0.0)
        roi = float(getattr(row, "roi", 0.0) or 0.0)

        if sample_size >= min_sample_size and hit_rate > 0:
            shrink_weight = 0.35

            if original_confidence - hit_rate >= 0.20:
                shrink_weight = 0.55
                reasons.append("Heavy overconfidence shrinkage applied.")
            elif original_confidence - hit_rate >= 0.12:
                shrink_weight = 0.45
                reasons.append("Moderate overconfidence shrinkage applied.")
            else:
                reasons.append("Light calibration shrinkage applied.")

            adjusted_confidence = (
                original_confidence * (1 - shrink_weight)
                + hit_rate * shrink_weight
            )

        if sample_size >= min_sample_size and roi < -0.10:
            adjusted_confidence *= 0.94
            reasons.append("Negative confidence-band ROI penalty applied.")

    market_cap = MARKET_CONFIDENCE_CAPS.get(market, 0.90)

    if adjusted_confidence > market_cap:
        adjusted_confidence = market_cap
        reasons.append(f"Market confidence cap applied: {market_cap}.")

    adjusted_confidence = max(
        min(adjusted_confidence, 0.97),
        0.01,
    )

    return {
        "raw_confidence": round(original_confidence, 4),
        "recalibrated_confidence": round(adjusted_confidence, 4),
        "confidence_band": confidence_band,
        "market_cap": market_cap,
        "reasons": reasons,
    }