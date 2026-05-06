# backend/app/ml/predict_football.py

import pickle

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import MatchOdds, Prediction, PredictionGroupItem
from app.features.football_features import MARKET_LABELS, MARKET_TARGETS, feature_columns, load_upcoming_frame
from app.ml.registry import load_model_metadata
from app.ml.train_football import metadata_path_for_market, model_path_for_market
from app.analysis.weak_markets import is_market_weak

def predict_all_football_markets(
    session: Session,
    slate: str,
    limit: int = 30,
    min_confidence: float = 0.6,
) -> int:
    session.execute(
        delete(PredictionGroupItem).where(PredictionGroupItem.slate == slate)
    )

    session.execute(
        delete(Prediction).where(Prediction.slate == slate)
    )

    session.commit()

    inserted = 0

    for market in MARKET_TARGETS.keys():
        if is_market_weak(session=session, market=market):
            print(f"[SKIPPED WEAK MARKET] {market}")
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
        print(f"[SKIPPED] Ensemble model file not found for {market}: {model_path}")
        return 0

    metadata = load_model_metadata(metadata_path)
    selected_model_name = metadata.get("selected_model_name", "WeightedEnsemble")

    with model_path.open("rb") as file:
        bundle = pickle.load(file)

    df = load_upcoming_frame(session, limit=limit)

    if df.empty:
        return 0

    df = df.reset_index(drop=True)

    model_feature_columns = bundle.get("feature_columns", feature_columns())
    x = df[model_feature_columns].fillna(0.0)

    probabilities = _predict_ensemble_probabilities(bundle=bundle, x=x)

    positive_label, negative_label = MARKET_LABELS[market]

    inserted = 0

    for row_index, row in df.iterrows():
        probability = float(probabilities[row_index])

        if probability >= 0.5:
            predicted_label = positive_label
            confidence = probability
        else:
            predicted_label = negative_label
            confidence = 1 - probability

        if confidence < min_confidence:
            continue

        odds = _find_odds(
            session=session,
            match_id=int(row["match_id"]),
            market=market,
            selection=predicted_label,
        )

        implied_probability = None
        value_score = None

        if odds:
            implied_probability = round(1 / odds, 4)
            value_score = round(confidence - implied_probability, 4)

        session.add(
            Prediction(
                slate=slate,
                match_id=int(row["match_id"]),
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


def _predict_ensemble_probabilities(bundle: dict, x):
    models = bundle["models"]
    weights = bundle["weights"]

    final_probability = None

    for model_name, model in models.items():
        probability = model.predict_proba(x)[:, 1]
        weighted_probability = probability * weights[model_name]

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
    odds_row = session.scalar(
        select(MatchOdds)
        .where(
            MatchOdds.match_id == match_id,
            MatchOdds.market == market,
            MatchOdds.selection == selection,
        )
        .order_by(MatchOdds.retrieved_at.desc())
    )

    if odds_row is None:
        return None

    return float(odds_row.odds)