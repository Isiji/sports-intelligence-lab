# backend/app/ml/predict_football.py

from pathlib import Path
import pickle

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Prediction, PredictionGroupItem
from app.features.football_features import feature_columns, load_upcoming_frame


HOME_WIN_MODEL_PATH = Path("artifacts/football_home_win_model.pkl")
OVER_2_5_MODEL_PATH = Path("artifacts/football_over_2_5_model.pkl")


def predict_football_home_win(
    session: Session,
    slate: str,
    limit: int = 16,
) -> int:
    return _predict_binary_market(
        session=session,
        slate=slate,
        limit=limit,
        model_path=HOME_WIN_MODEL_PATH,
        model_name="football_home_win_best_model",
        market="home_win",
        positive_label="HOME_WIN",
        negative_label="NOT_HOME_WIN",
    )


def predict_football_over_2_5(
    session: Session,
    slate: str,
    limit: int = 16,
) -> int:
    return _predict_binary_market(
        session=session,
        slate=slate,
        limit=limit,
        model_path=OVER_2_5_MODEL_PATH,
        model_name="football_over_2_5_best_model",
        market="over_2_5_goals",
        positive_label="OVER_2_5",
        negative_label="UNDER_2_5",
    )


def predict_all_football_markets(
    session: Session,
    slate: str,
    limit: int = 16,
) -> int:
    """
    Runs all football prediction markets.

    Important:
    We delete old group items first because prediction_group_items
    depends on predictions through a foreign key.
    """

    session.execute(
        delete(PredictionGroupItem).where(PredictionGroupItem.slate == slate)
    )

    session.execute(
        delete(Prediction).where(Prediction.slate == slate)
    )

    session.commit()

    inserted = 0

    inserted += predict_football_home_win(
        session=session,
        slate=slate,
        limit=limit,
    )

    inserted += predict_football_over_2_5(
        session=session,
        slate=slate,
        limit=limit,
    )

    return inserted


def _predict_binary_market(
    session: Session,
    slate: str,
    limit: int,
    model_path: Path,
    model_name: str,
    market: str,
    positive_label: str,
    negative_label: str,
) -> int:
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}. Train model first.")

    with model_path.open("rb") as file:
        model = pickle.load(file)

    df = load_upcoming_frame(session, limit=limit)

    if df.empty:
        return 0

    df = df.reset_index(drop=True)
    x = df[feature_columns()].fillna(0.0)

    probabilities = model.predict_proba(x)

    inserted = 0

    for row_index, row in df.iterrows():
        probability = float(probabilities[row_index][1])

        if probability >= 0.5:
            predicted_label = positive_label
            confidence = probability
        else:
            predicted_label = negative_label
            confidence = 1 - probability

        session.add(
            Prediction(
                slate=slate,
                match_id=int(row["match_id"]),
                sport="football",
                model_name=model_name,
                market=market,
                predicted_label=predicted_label,
                confidence=round(confidence, 4),
            )
        )

        inserted += 1

    session.commit()

    return inserted