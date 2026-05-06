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
from app.features.football_features import (
    MARKET_TARGETS,
    feature_columns,
    load_training_frame,
)
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

    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    print(f"\nTraining frame loaded: {len(df)} matches")
    print(f"Date range: {df['kickoff_date'].min()} → {df['kickoff_date'].max()}")

    for market, target_column in MARKET_TARGETS.items():
        if target_column not in df.columns:
            print(f"[SKIPPED] {market}: target column missing.")
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

    train_df, test_df = _chronological_split(df)

    if train_df[target_column].nunique() < 2:
        raise ValueError("training split has only one class.")

    if test_df[target_column].nunique() < 2:
        raise ValueError("testing split has only one class.")

    x_train = train_df[feature_columns()].fillna(0.0)
    y_train = train_df[target_column]

    x_test = test_df[feature_columns()].fillna(0.0)
    y_test = test_df[target_column]

    candidates = _candidate_models()

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

    best = _select_best_model(results)

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
            "precision": round(best["precision"], 4),
            "recall": round(best["recall"], 4),
            "f1": round(best["f1"], 4),
            "log_loss": round(best["log_loss"], 4),
            "brier_score": round(best["brier_score"], 4),
            "roc_auc": round(best["roc_auc"], 4),
            "train_size": len(train_df),
            "test_size": len(test_df),
            "split_type": "chronological_80_20",
            "train_start": str(train_df["kickoff_date"].min()),
            "train_end": str(train_df["kickoff_date"].max()),
            "test_start": str(test_df["kickoff_date"].min()),
            "test_end": str(test_df["kickoff_date"].max()),
        },
    )

    print(f"\n[{market}] Chronological model comparison:")
    print(
        f"Train: {len(train_df)} matches "
        f"({train_df['kickoff_date'].min()} → {train_df['kickoff_date'].max()})"
    )
    print(
        f"Test: {len(test_df)} matches "
        f"({test_df['kickoff_date'].min()} → {test_df['kickoff_date'].max()})"
    )

    for result in results:
        print(
            f"{result['model_name']}: "
            f"accuracy={round(result['accuracy'], 4)}, "
            f"f1={round(result['f1'], 4)}, "
            f"brier={round(result['brier_score'], 4)}, "
            f"roc_auc={round(result['roc_auc'], 4)}"
        )

    print(f"Selected: {best['model_name']} ({round(best['accuracy'], 4)})\n")


def _chronological_split(df):
    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    if len(df) < 50:
        raise ValueError("Need at least 50 played matches for reliable chronological split.")

    split_index = int(len(df) * 0.8)

    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    if train_df.empty or test_df.empty:
        raise ValueError("Chronological split produced empty train or test set.")

    if train_df["kickoff_date"].max() >= test_df["kickoff_date"].min():
        raise ValueError("Invalid chronological split: train overlaps with test.")

    return train_df, test_df


def _candidate_models() -> dict[str, object]:
    return {
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


def _calculate_metrics(y_true, y_pred, probabilities) -> dict[str, float]:
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "brier_score": brier_score_loss(y_true, probabilities),
        "log_loss": 0.0,
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


def _select_best_model(results: list[dict]) -> dict:
    """
    Selection priority:
    1. Lower Brier score = better probability quality.
    2. Higher ROC AUC = better ranking ability.
    3. Higher F1 = better balance.
    4. Higher accuracy.
    """

    return sorted(
        results,
        key=lambda item: (
            item["brier_score"],
            -item["roc_auc"],
            -item["f1"],
            -item["accuracy"],
        ),
    )[0]