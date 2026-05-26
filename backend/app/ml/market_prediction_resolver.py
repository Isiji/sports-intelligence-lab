# backend/app/ml/market_prediction_resolver.py

from __future__ import annotations

from dataclasses import dataclass

from app.features.football_features import MARKET_LABELS


POSITIVE_SIDE_ONLY_MARKETS = {
    "btts_yes",
    "btts_no",
    "over_1_5_goals",
    "under_1_5_goals",
    "over_2_5_goals",
    "under_2_5_goals",
    "over_3_5_goals",
    "under_3_5_goals",
    "corners_over_8_5",
    "shots_on_target_over_8_5",
}

RESEARCH_DERIVATIVE_MARKETS = {
    "ht_ft",
    "exact_score",
    "first_half_exact_score",
}


@dataclass(frozen=True)
class ResolvedPrediction:
    predicted_label: str | None
    confidence: float
    probability: float
    is_positive_side: bool
    should_save: bool


def resolve_market_prediction(
    *,
    market: str,
    probability: float,
) -> ResolvedPrediction:
    if market not in MARKET_LABELS:
        return ResolvedPrediction(
            predicted_label=None,
            confidence=0.0,
            probability=float(probability),
            is_positive_side=False,
            should_save=False,
        )

    positive_label, negative_label = MARKET_LABELS[market]
    probability = float(probability)

    if probability >= 0.5:
        return ResolvedPrediction(
            predicted_label=positive_label,
            confidence=probability,
            probability=probability,
            is_positive_side=True,
            should_save=True,
        )

    if market in POSITIVE_SIDE_ONLY_MARKETS:
        return ResolvedPrediction(
            predicted_label=None,
            confidence=1.0 - probability,
            probability=probability,
            is_positive_side=False,
            should_save=False,
        )

    return ResolvedPrediction(
        predicted_label=negative_label,
        confidence=1.0 - probability,
        probability=probability,
        is_positive_side=False,
        should_save=True,
    )