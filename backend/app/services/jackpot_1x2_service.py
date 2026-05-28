# backend/app/services/jackpot_1x2_service.py

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Match
from app.features.football_features import load_single_match_frame
from app.ml.predict_football import (
    _load_model_bundle,
    _predict_probabilities,
)
from app.ml.train_football import model_path_for_market


MARKETS = [
    "home_win",
    "draw",
    "away_win",
]


def analyze_match_1x2(
    session: Session,
    match_id: int,
) -> dict:

    match = session.get(Match, match_id)

    if not match:
        raise ValueError("Match not found.")

    if match.is_finished:
        raise ValueError("Match already finished.")

    if match.is_cancelled:
        raise ValueError("Match cancelled.")

    if match.is_postponed:
        raise ValueError("Match postponed.")

    frame = load_single_match_frame(
        session=session,
        match_id=match_id,
    )

    if frame.empty:
        raise ValueError(
            "Match features unavailable."
        )

    raw_probabilities: dict[str, float] = {}

    for market in MARKETS:

        model_path = model_path_for_market(
            market
        )

        bundle = _load_model_bundle(
            model_path
        )

        feature_columns = bundle.get(
            "feature_columns",
            [],
        )

        if not feature_columns:
            raise ValueError(
                f"Missing feature columns for {market}"
            )

        missing_features = [
            feature
            for feature in feature_columns
            if feature not in frame.columns
        ]

        if missing_features:
            raise ValueError(
                f"Missing features for {market}: "
                f"{missing_features[:10]}"
            )

        x = frame[
            feature_columns
        ].fillna(0.0)

        probability = float(
            _predict_probabilities(
                bundle=bundle,
                x=x,
            )[0]
        )

        raw_probabilities[
            market
        ] = probability

    total = sum(
        raw_probabilities.values()
    )

    if total <= 0:
        raise ValueError(
            "Unable to calculate 1X2 probabilities."
        )

    home_probability = (
        raw_probabilities["home_win"]
        / total
    )

    draw_probability = (
        raw_probabilities["draw"]
        / total
    )

    away_probability = (
        raw_probabilities["away_win"]
        / total
    )

    ranked = sorted(
        [
            (
                "1",
                "HOME_WIN",
                home_probability,
            ),
            (
                "X",
                "DRAW",
                draw_probability,
            ),
            (
                "2",
                "AWAY_WIN",
                away_probability,
            ),
        ],
        key=lambda item: item[2],
        reverse=True,
    )

    best = ranked[0]
    second = ranked[1]

    confidence = float(
        best[2]
    )

    margin = float(
        best[2] - second[2]
    )

    if (
        confidence >= 0.60
        and margin >= 0.12
    ):
        risk_level = "LOW"

    elif (
        confidence >= 0.50
        and margin >= 0.08
    ):
        risk_level = "MEDIUM"

    else:
        risk_level = "HIGH"

    if confidence >= 0.55:
        verdict = "STRONG"

    elif confidence >= 0.45:
        verdict = "LEAN"

    else:
        verdict = "UNCERTAIN"

    one_x = (
        home_probability
        + draw_probability
    )

    x_two = (
        draw_probability
        + away_probability
    )

    one_two = (
        home_probability
        + away_probability
    )

    double_chances = sorted(
        [
            ("1X", one_x),
            ("X2", x_two),
            ("12", one_two),
        ],
        key=lambda x: x[1],
        reverse=True,
    )

    best_double_chance = {
        "pick": double_chances[0][0],
        "probability": round(
            double_chances[0][1],
            4,
        ),
    }

    confidence_band = (
        "VERY_STRONG"
        if confidence >= 0.65
        else "STRONG"
        if confidence >= 0.55
        else "MODERATE"
        if confidence >= 0.45
        else "WEAK"
    )

    reasoning = []

    if best[0] == "1":
        reasoning.append(
            "Home win is the highest-rated outcome."
        )

    elif best[0] == "X":
        reasoning.append(
            "Draw is the highest-rated outcome."
        )

    else:
        reasoning.append(
            "Away win is the highest-rated outcome."
        )

    if margin < 0.05:
        reasoning.append(
            "Very small separation between top outcomes."
        )

    elif margin < 0.10:
        reasoning.append(
            "Moderate separation between top outcomes."
        )

    else:
        reasoning.append(
            "Clear separation from alternative outcomes."
        )

    if best_double_chance["probability"] >= 0.75:
        safe_pick = "VERY_STRONG_DOUBLE_CHANCE"

    elif best_double_chance["probability"] >= 0.65:
        safe_pick = "STRONG_DOUBLE_CHANCE"

    else:
        safe_pick = "NO_SAFE_DOUBLE_CHANCE"

    return {
        "temporary_analysis": True,
        "source_type": "jackpot_1x2",

        "match": {
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "league": match.league,
            "season": match.season,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "kickoff_date": (
                str(match.kickoff_date)
                if match.kickoff_date
                else None
            ),
            "kickoff_datetime": (
                match.kickoff_datetime.isoformat()
                if match.kickoff_datetime
                else None
            ),
        },

        "home_win_probability": round(
            home_probability,
            4,
        ),

        "draw_probability": round(
            draw_probability,
            4,
        ),

        "away_win_probability": round(
            away_probability,
            4,
        ),

        "recommended_pick": best[0],

        "recommended_label": best[1],

        "confidence": round(
            confidence,
            4,
        ),

        "confidence_band": (
            confidence_band
        ),

        "margin": round(
            margin,
            4,
        ),

        "risk_level": risk_level,

        "verdict": verdict,

        "reasoning": reasoning,

        "best_double_chance": (
            best_double_chance
        ),

        "recommended_safe_pick": (
            safe_pick
        ),

        "alternatives": [
            {
                "pick": ranked[1][0],
                "label": ranked[1][1],
                "probability": round(
                    ranked[1][2],
                    4,
                ),
            },
            {
                "pick": ranked[2][0],
                "label": ranked[2][1],
                "probability": round(
                    ranked[2][2],
                    4,
                ),
            },
        ],
    }