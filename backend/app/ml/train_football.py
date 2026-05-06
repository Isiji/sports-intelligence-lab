# backend/app/ml/train_football.py

from pathlib import Path
import pickle

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sqlalchemy.orm import Session

from app.db.models import ModelTrainingRun
from app.features.football_features import MARKET_TARGETS, feature_columns, load_training_frame
from app.ml.registry import save_model_metadata


ARTIFACT_DIR = Path("artifacts")


def model_path_for_market(market: str) -> Path:
    return ARTIFACT_DIR / f"football_{market}_model.pkl"


def metadata_path_for_market(market: str) -> Path:
    return ARTIFACT_DIR / f"football_{market}_model.json"


def train_all_football_models(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    for market, target_column in MARKET_TARGETS.items():
        if target_column not in df.columns:
            continue

        try:
            _train_and_select_model(
                session=session,
                df=df,
                market=market,
                target_column=target_column,
            )
        except ValueError as exc:
            print(f"[SKIPPED] {market}: {exc}")


def _train_and_select_model(
    session: Session,
    df,
    market: str,
    target_column: str,
) -> None:
    if df[target_column].nunique() < 2:
        raise ValueError("target has only one class.")

    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    split_index = int(len(df) * 0.8)

    if split_index < 20:
        raise ValueError("not enough historical data for time-based split.")

    train_df = df.iloc[:split_index]
    test_df = df.iloc[split_index:]

    if test_df.empty:
        raise ValueError("empty test split.")

    x_train = train_df[feature_columns()].fillna(0.0)
    y_train = train_df[target_column]

    x_test = test_df[feature_columns()].fillna(0.0)
    y_test = test_df[target_column]

    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError("train/test split does not contain both classes.")

    candidates = {
        "LogisticRegression": Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "model",
                    CalibratedClassifierCV(
                        estimator=LogisticRegression(max_iter=2000),
                        cv=3,
                        method="isotonic",
                    ),
                ),
            ]
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            max_depth=14,
            min_samples_split=4,
            min_samples_leaf=2,
            random_state=42,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.04,
            max_leaf_nodes=31,
            random_state=42,
        ),
    }

    results: list[dict] = []

    for model_name, model in candidates.items():
        model.fit(x_train, y_train)

        predicted = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1]

        metrics = _calculate_metrics(
            y_true=y_test,
            y_pred=predicted,
            probabilities=probabilities,
        )

        results.append(
            {
                "model_name": model_name,
                "model": model,
                **metrics,
            }
        )

    best = max(
        results,
        key=lambda item: (
            item["brier_score"] * -1,
            item["accuracy"],
            item["f1"],
        ),
    )

    for result in results:
        session.add(
            ModelTrainingRun(
                sport="football",
                market=market,
                model_name=result["model_name"],
                accuracy=round(result["accuracy"], 4),
                precision=round(result["precision"], 4),
                recall=round(result["recall"], 4),
                f1=round(result["f1"], 4),
                log_loss=round(result["log_loss"], 4),
                brier_score=round(result["brier_score"], 4),
                roc_auc=round(result["roc_auc"], 4),
                train_size=len(train_df),
                test_size=len(test_df),
                selected=1 if result["model_name"] == best["model_name"] else 0,
            )
        )

    session.commit()

    save_path = model_path_for_market(market)
    metadata_path = metadata_path_for_market(market)

    save_path.parent.mkdir(parents=True, exist_ok=True)

    with save_path.open("wb") as file:
        pickle.dump(best["model"], file)

    save_model_metadata(
        metadata_path=metadata_path,
        market=market,
        selected_model_name=best["model_name"],
        selected_accuracy=best["accuracy"],
        feature_columns=feature_columns(),
        extra={
            "precision": best["precision"],
            "recall": best["recall"],
            "f1": best["f1"],
            "log_loss": best["log_loss"],
            "brier_score": best["brier_score"],
            "roc_auc": best["roc_auc"],
            "train_size": len(train_df),
            "test_size": len(test_df),
            "split_type": "time_based_80_20",
        },
    )

    print(f"\n[{market}] Model comparison:")
    for result in results:
        print(
            result["model_name"],
            "accuracy=", round(result["accuracy"], 4),
            "f1=", round(result["f1"], 4),
            "brier=", round(result["brier_score"], 4),
        )

    print(f"Selected: {best['model_name']} ({round(best['accuracy'], 4)})\n")


def _calculate_metrics(y_true, y_pred, probabilities) -> dict[str, float]:
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "log_loss": 0.0,
        "brier_score": brier_score_loss(y_true, probabilities),
        "roc_auc": 0.0,
    }

    try:
        metrics["log_loss"] = log_loss(y_true, probabilities)
    except ValueError:
        metrics["log_loss"] = 0.0

    try:
        metrics["roc_auc"] = roc_auc_score(y_true, probabilities)
    except ValueError:
        metrics["roc_auc"] = 0.0

    return {key: float(value) for key, value in metrics.items()}