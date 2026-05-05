# backend/app/ml/train_football.py

from pathlib import Path
import pickle

from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sqlalchemy.orm import Session

from app.features.football_features import feature_columns, load_training_frame


MODEL_PATH = Path("artifacts/football_home_win_model.pkl")


def train_football_home_win_model(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found. Run seed-demo or ingest historical data first.")

    x = df[feature_columns()]
    y = df["target_home_win"]

    base_model = LogisticRegression(max_iter=1000)

    model = CalibratedClassifierCV(
        estimator=base_model,
        cv=3,
        method="isotonic",
    )

    model.fit(x, y)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with MODEL_PATH.open("wb") as file:
        pickle.dump(model, file)