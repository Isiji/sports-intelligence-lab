# backend/app/ml/train_football.py

from pathlib import Path
import pickle

from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sqlalchemy.orm import Session

from app.features.football_features import feature_columns, load_training_frame


HOME_WIN_MODEL_PATH = Path("artifacts/football_home_win_model.pkl")
OVER_2_5_MODEL_PATH = Path("artifacts/football_over_2_5_model.pkl")


def train_football_home_win_model(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found. Run seed-demo or ingest historical data first.")

    model = _train_binary_classifier(
        x=df[feature_columns()],
        y=df["target_home_win"],
    )

    HOME_WIN_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with HOME_WIN_MODEL_PATH.open("wb") as file:
        pickle.dump(model, file)


def train_football_over_2_5_model(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found. Run seed-demo or ingest historical data first.")

    model = _train_binary_classifier(
        x=df[feature_columns()],
        y=df["target_over_2_5"],
    )

    OVER_2_5_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OVER_2_5_MODEL_PATH.open("wb") as file:
        pickle.dump(model, file)


def train_all_football_models(session: Session) -> None:
    train_football_home_win_model(session)
    train_football_over_2_5_model(session)


def _train_binary_classifier(x, y):
    base_model = LogisticRegression(max_iter=1000)

    model = CalibratedClassifierCV(
        estimator=base_model,
        cv=3,
        method="isotonic",
    )

    model.fit(x, y)

    return model