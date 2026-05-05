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
        model_name="football_home_win_baseline_v1",
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
        model_name="football_over_2_5_baseline_v1",
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
    IMPORTANT:
    We must delete group items FIRST before deleting predictions
    due to foreign key constraints.
    """

    # ✅ Step 1: delete groups
    session.execute(
        delete(PredictionGroupItem).where(PredictionGroupItem.slate == slate)
    )

    # ✅ Step 2: delete predictions
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

# VERY IMPORTANT FIX
    df = df.reset_index(drop=True)
    
    if df.empty:
        return 0

    probabilities = model.predict_proba(df[feature_columns()])

    inserted = 0

    for row_index, row in df.iterrows():
        prob = float(probabilities[row_index][1])

        if prob >= 0.5:
            predicted_label = positive_label
            confidence = prob
        else:
            predicted_label = negative_label
            confidence = 1 - prob

        prediction = Prediction(
            slate=slate,
            match_id=int(row["match_id"]),
            sport="football",
            model_name=model_name,
            market=market,
            predicted_label=predicted_label,
            confidence=round(confidence, 4),
        )

        session.add(prediction)
        inserted += 1

    session.commit()

    return inserted