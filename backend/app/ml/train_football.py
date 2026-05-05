# backend/app/ml/train_football.py

from pathlib import Path
import pickle

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from sqlalchemy.orm import Session

from app.db.models import ModelTrainingRun
from app.features.football_features import feature_columns, load_training_frame


HOME_WIN_MODEL_PATH = Path("artifacts/football_home_win_model.pkl")
OVER_2_5_MODEL_PATH = Path("artifacts/football_over_2_5_model.pkl")


def train_all_football_models(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    x = df[feature_columns()]

    _train_and_select_model(
        session=session,
        x=x,
        y=df["target_home_win"],
        save_path=HOME_WIN_MODEL_PATH,
        market="home_win",
    )

    _train_and_select_model(
        session=session,
        x=x,
        y=df["target_over_2_5"],
        save_path=OVER_2_5_MODEL_PATH,
        market="over_2_5_goals",
    )


def train_football_home_win_model(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    _train_and_select_model(
        session=session,
        x=df[feature_columns()],
        y=df["target_home_win"],
        save_path=HOME_WIN_MODEL_PATH,
        market="home_win",
    )


def train_football_over_2_5_model(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    _train_and_select_model(
        session=session,
        x=df[feature_columns()],
        y=df["target_over_2_5"],
        save_path=OVER_2_5_MODEL_PATH,
        market="over_2_5_goals",
    )


def _train_and_select_model(
    session: Session,
    x,
    y,
    save_path: Path,
    market: str,
) -> None:
    """
    Train candidate models, compare them, save the best model,
    and store all candidate results in the database.
    """

    x = x.fillna(0.0)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y if y.nunique() > 1 else None,
    )

    candidates = {
        "LogisticRegression": CalibratedClassifierCV(
            estimator=LogisticRegression(max_iter=1000),
            cv=3,
            method="isotonic",
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            random_state=42,
        ),
    }

    results: list[tuple[str, object, float]] = []

    for model_name, model in candidates.items():
        model.fit(x_train, y_train)

        predictions = model.predict(x_test)
        accuracy = accuracy_score(y_test, predictions)

        results.append((model_name, model, float(accuracy)))

    best_model_name, best_model, best_accuracy = max(
        results,
        key=lambda item: item[2],
    )

    for model_name, _, accuracy in results:
        session.add(
            ModelTrainingRun(
                sport="football",
                market=market,
                model_name=model_name,
                accuracy=round(accuracy, 4),
                selected=1 if model_name == best_model_name else 0,
            )
        )

    session.commit()

    save_path.parent.mkdir(parents=True, exist_ok=True)

    with save_path.open("wb") as file:
        pickle.dump(best_model, file)

    print(f"\n[{market}] Model comparison:")
    for model_name, _, accuracy in results:
        print(f"{model_name}: {round(accuracy, 4)}")

    print(f"Selected: {best_model_name} ({round(best_accuracy, 4)})\n")