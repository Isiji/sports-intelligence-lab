# backend/app/ml/train_football.py

from pathlib import Path
import pickle

from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from sqlalchemy.orm import Session

from app.features.football_features import feature_columns, load_training_frame


HOME_WIN_MODEL_PATH = Path("artifacts/football_home_win_model.pkl")
OVER_2_5_MODEL_PATH = Path("artifacts/football_over_2_5_model.pkl")


def train_all_football_models(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    x = df[feature_columns()]

    _train_and_select_model(
        x,
        df["target_home_win"],
        HOME_WIN_MODEL_PATH,
        "HOME_WIN"
    )

    _train_and_select_model(
        x,
        df["target_over_2_5"],
        OVER_2_5_MODEL_PATH,
        "OVER_2_5"
    )


# ---------- CORE ENGINE ----------

def _train_and_select_model(x, y, save_path: Path, label: str):
    """
    Train multiple models and select the best one.
    """

    X_train, X_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42
    )

    # -------- MODEL 1: Logistic Regression --------
    log_model = CalibratedClassifierCV(
        estimator=LogisticRegression(max_iter=1000),
        cv=3,
        method="isotonic",
    )
    log_model.fit(X_train, y_train)
    log_preds = log_model.predict(X_test)
    log_acc = accuracy_score(y_test, log_preds)

    # -------- MODEL 2: Random Forest --------
    rf_model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        random_state=42,
    )
    rf_model.fit(X_train, y_train)
    rf_preds = rf_model.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_preds)

    # -------- COMPARE --------
    if rf_acc > log_acc:
        best_model = rf_model
        best_name = "RandomForest"
        best_acc = rf_acc
    else:
        best_model = log_model
        best_name = "LogisticRegression"
        best_acc = log_acc

    print(f"\n[{label}] Model comparison:")
    print(f"LogisticRegression accuracy: {round(log_acc,4)}")
    print(f"RandomForest accuracy: {round(rf_acc,4)}")
    print(f"Selected: {best_name} ({round(best_acc,4)})\n")

    save_path.parent.mkdir(parents=True, exist_ok=True)

    with save_path.open("wb") as f:
        pickle.dump(best_model, f)