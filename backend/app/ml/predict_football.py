# backend/app/ml/predict_football.py

import pickle

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analysis.weak_markets import is_market_weak
from app.db.models import Match, MatchOdds, Prediction, PredictionGroupItem
from app.features.football_features import (
    MARKET_LABELS,
    MARKET_TARGETS,
    feature_columns,
    load_upcoming_frame,
)
from app.ml.registry import load_model_metadata
from app.ml.train_football import metadata_path_for_market, model_path_for_market
from app.services.prediction_guard_service import apply_prediction_guard
from app.services.prediction_intelligence_service import (
    apply_prediction_intelligence,
)


def predict_all_football_markets(
    session: Session,
    slate: str,
    limit: int = 30,
    min_confidence: float = 0.6,
) -> int:
    session.execute(
        delete(PredictionGroupItem).where(
            PredictionGroupItem.slate == slate
        )
    )

    session.execute(
        delete(Prediction).where(
            Prediction.slate == slate
        )
    )

    session.commit()

    inserted = 0

    for market in MARKET_TARGETS.keys():
        if is_market_weak(
            session=session,
            market=market,
        ):
            print(
                f"[SKIPPED OLD WEAK MARKET CHECK] {market}"
            )
            continue

        inserted += predict_football_market(
            session=session,
            slate=slate,
            market=market,
            limit=limit,
            min_confidence=min_confidence,
        )

    return inserted


def predict_football_market(
    session: Session,
    slate: str,
    market: str,
    limit: int = 30,
    min_confidence: float = 0.6,
) -> int:
    model_path = model_path_for_market(market)
    metadata_path = metadata_path_for_market(market)

    if not model_path.exists():
        print(
            f"[SKIPPED] Ensemble model file not found "
            f"for {market}: {model_path}"
        )
        return 0

    metadata = load_model_metadata(metadata_path)

    selected_model_name = metadata.get(
        "selected_model_name",
        "WeightedEnsemble",
    )

    with model_path.open("rb") as file:
        bundle = pickle.load(file)

    df = load_upcoming_frame(
        session,
        limit=limit,
    )

    if df.empty:
        return 0

    df = df.reset_index(drop=True)

    model_feature_columns = bundle.get(
        "feature_columns",
        feature_columns(),
    )

    x = df[model_feature_columns].fillna(0.0)

    probabilities = _predict_ensemble_probabilities(
        bundle=bundle,
        x=x,
    )

    positive_label, negative_label = MARKET_LABELS[market]

    inserted = 0

    for row_index, row in df.iterrows():
        match_id = int(row["match_id"])

        match = session.scalar(
            select(Match).where(
                Match.id == match_id
            )
        )

        if match is None:
            continue

        probability = float(
            probabilities[row_index]
        )

        if probability >= 0.5:
            predicted_label = positive_label
            confidence = probability
        else:
            predicted_label = negative_label
            confidence = 1 - probability

        guard = apply_prediction_guard(
            session=session,
            match=match,
            market=market,
            raw_confidence=confidence,
        )

        if not guard["allowed"]:
            print(
                f"[GUARD BLOCKED] "
                f"match_id={match_id}, "
                f"market={market}, "
                f"reasons={guard['reasons']}"
            )
            continue

        confidence = float(
            guard["adjusted_confidence"]
        )

        odds = _find_odds(
            session=session,
            match_id=match_id,
            market=market,
            selection=predicted_label,
        )

        intelligence = apply_prediction_intelligence(
            session=session,
            match=match,
            market=market,
            raw_confidence=confidence,
            odds=odds,
        )

        if not intelligence["allowed"]:
            print(
                f"[INTELLIGENCE BLOCKED] "
                f"match_id={match_id}, "
                f"market={market}, "
                f"reasons={intelligence['reasons']}"
            )
            continue

        confidence = float(
            intelligence["adjusted_confidence"]
        )

        if confidence < min_confidence:
            print(
                f"[LOW CONFIDENCE AFTER INTELLIGENCE] "
                f"match_id={match_id}, "
                f"market={market}, "
                f"confidence={confidence}"
            )
            continue

        implied_probability = None
        value_score = None

        if odds:
            implied_probability = round(
                1 / odds,
                4,
            )

            value_score = round(
                confidence - implied_probability,
                4,
            )

        session.add(
            Prediction(
                slate=slate,
                match_id=match_id,
                sport="football",
                model_name=selected_model_name,
                market=market,
                predicted_label=predicted_label,
                confidence=round(confidence, 4),
                odds=odds,
                implied_probability=implied_probability,
                value_score=value_score,
            )
        )

        inserted += 1

    session.commit()

    return inserted


def _predict_ensemble_probabilities(
    bundle: dict,
    x,
):
    models = bundle["models"]

    weights = bundle["weights"]

    final_probability = None

    for model_name, model in models.items():
        probability = model.predict_proba(x)[:, 1]

        weighted_probability = (
            probability
            * weights[model_name]
        )

        if final_probability is None:
            final_probability = weighted_probability
        else:
            final_probability += weighted_probability

    return final_probability


def _find_odds(
    session: Session,
    match_id: int,
    market: str,
    selection: str,
) -> float | None:
    odds_lookup_mapping = {
        ("home_win", "HOME_WIN"): (
            "home_win",
            "HOME_WIN",
        ),

        ("home_win", "NOT_HOME_WIN"): (
            "away_win",
            "AWAY_WIN",
        ),

        ("away_win", "AWAY_WIN"): (
            "away_win",
            "AWAY_WIN",
        ),

        ("away_win", "NOT_AWAY_WIN"): (
            "home_win",
            "HOME_WIN",
        ),

        ("draw", "DRAW"): (
            "draw",
            "DRAW",
        ),

        ("draw", "NOT_DRAW"): (
            "double_chance_12",
            "DOUBLE_CHANCE_12",
        ),

        ("over_1_5_goals", "OVER_1_5"): (
            "over_1_5_goals",
            "OVER_1_5",
        ),

        ("over_1_5_goals", "UNDER_1_5"): (
            "under_1_5_goals",
            "UNDER_1_5",
        ),

        ("under_1_5_goals", "UNDER_1_5"): (
            "under_1_5_goals",
            "UNDER_1_5",
        ),

        ("under_1_5_goals", "OVER_1_5"): (
            "over_1_5_goals",
            "OVER_1_5",
        ),

        ("over_2_5_goals", "OVER_2_5"): (
            "over_2_5_goals",
            "OVER_2_5",
        ),

        ("over_2_5_goals", "UNDER_2_5"): (
            "under_2_5_goals",
            "UNDER_2_5",
        ),

        ("under_2_5_goals", "UNDER_2_5"): (
            "under_2_5_goals",
            "UNDER_2_5",
        ),

        ("under_2_5_goals", "OVER_2_5"): (
            "over_2_5_goals",
            "OVER_2_5",
        ),

        ("over_3_5_goals", "OVER_3_5"): (
            "over_3_5_goals",
            "OVER_3_5",
        ),

        ("over_3_5_goals", "UNDER_3_5"): (
            "under_3_5_goals",
            "UNDER_3_5",
        ),

        ("under_3_5_goals", "UNDER_3_5"): (
            "under_3_5_goals",
            "UNDER_3_5",
        ),

        ("under_3_5_goals", "OVER_3_5"): (
            "over_3_5_goals",
            "OVER_3_5",
        ),

        ("btts_yes", "BTTS_YES"): (
            "btts_yes",
            "BTTS_YES",
        ),

        ("btts_yes", "BTTS_NO"): (
            "btts_no",
            "BTTS_NO",
        ),

        ("double_chance_x2", "DOUBLE_CHANCE_X2"): (
            "double_chance_x2",
            "DOUBLE_CHANCE_X2",
        ),

        ("double_chance_x2", "NOT_DOUBLE_CHANCE_X2"): (
            "home_win",
            "HOME_WIN",
        ),

        ("double_chance_1x", "DOUBLE_CHANCE_1X"): (
            "double_chance_1x",
            "DOUBLE_CHANCE_1X",
        ),

        ("double_chance_1x", "NOT_DOUBLE_CHANCE_1X"): (
            "away_win",
            "AWAY_WIN",
        ),

        ("double_chance_12", "DOUBLE_CHANCE_12"): (
            "double_chance_12",
            "DOUBLE_CHANCE_12",
        ),

        ("double_chance_12", "NOT_DOUBLE_CHANCE_12"): (
            "draw",
            "DRAW",
        ),
    }

    lookup_market, lookup_selection = odds_lookup_mapping.get(
        (market, selection),
        (market, selection),
    )

    odds_row = session.scalar(
        select(MatchOdds)
        .where(
            MatchOdds.match_id == match_id,
            MatchOdds.market == lookup_market,
            MatchOdds.selection == lookup_selection,
        )
        .order_by(
            MatchOdds.retrieved_at.desc()
        )
    )

    if odds_row is None:
        print(
            "[ODDS MISS]",
            f"prediction_market={market}",
            f"prediction_selection={selection}",
            f"lookup_market={lookup_market}",
            f"lookup_selection={lookup_selection}",
            f"match_id={match_id}",
        )

        return None

    return float(odds_row.odds)