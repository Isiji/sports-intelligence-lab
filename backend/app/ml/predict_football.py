# backend/app/ml/predict_football.py

from pathlib import Path
import pickle

from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.features.football_features import feature_columns, load_upcoming_frame


MODEL_PATH = Path("artifacts/football_home_win_model.pkl")


def predict_football_home_win(
    session: Session,
    slate: str,
    limit: int = 16,
) -> int:
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Model file not found. Run train-football first.")

    with MODEL_PATH.open("rb") as file:
        model = pickle.load(file)

    df = load_upcoming_frame(session, limit=limit)

    if df.empty:
        return 0

    probabilities = model.predict_proba(df[feature_columns()])

    inserted = 0

    for row_index, row in df.iterrows():
        home_win_probability = float(probabilities[row_index][1])

        if home_win_probability >= 0.5:
            predicted_label = "HOME_WIN"
            confidence = home_win_probability
        else:
            predicted_label = "NOT_HOME_WIN"
            confidence = 1 - home_win_probability

        prediction = Prediction(
            slate=slate,
            match_id=int(row["match_id"]),
            sport="football",
            model_name="football_home_win_baseline_v1",
            market="home_win",
            predicted_label=predicted_label,
            confidence=round(confidence, 4),
        )

        session.add(prediction)
        inserted += 1

    session.commit()

    return inserted