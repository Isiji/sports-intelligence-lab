# backend/app/backtest/rolling.py

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sqlalchemy.orm import Session

from app.features.football_features import MARKET_TARGETS, feature_columns, load_training_frame


def run_rolling_backtest(
    session: Session,
    market: str = "home_win",
    initial_train_size: int = 60,
    test_window_size: int = 20,
) -> dict:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    if market not in MARKET_TARGETS:
        raise ValueError(f"Unsupported market: {market}")

    target_column = MARKET_TARGETS[market]

    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    if len(df) < initial_train_size + test_window_size:
        raise ValueError(
            f"Need at least {initial_train_size + test_window_size} played matches "
            f"for rolling backtest."
        )

    windows = []
    start_test_index = initial_train_size

    while start_test_index + test_window_size <= len(df):
        train_df = df.iloc[:start_test_index].copy()
        test_df = df.iloc[start_test_index:start_test_index + test_window_size].copy()

        if train_df[target_column].nunique() < 2 or test_df[target_column].nunique() < 2:
            start_test_index += test_window_size
            continue

        result = _evaluate_window(
            train_df=train_df,
            test_df=test_df,
            target_column=target_column,
        )

        result["train_start"] = str(train_df["kickoff_date"].min())
        result["train_end"] = str(train_df["kickoff_date"].max())
        result["test_start"] = str(test_df["kickoff_date"].min())
        result["test_end"] = str(test_df["kickoff_date"].max())
        result["train_size"] = len(train_df)
        result["test_size"] = len(test_df)

        windows.append(result)

        start_test_index += test_window_size

    if not windows:
        raise ValueError("No valid rolling windows were created.")

    return {
        "market": market,
        "initial_train_size": initial_train_size,
        "test_window_size": test_window_size,
        "windows": windows,
        "summary": _summarize_windows(windows),
    }


def _evaluate_window(train_df, test_df, target_column: str) -> dict:
    x_train = train_df[feature_columns()].fillna(0.0)
    y_train = train_df[target_column]

    x_test = test_df[feature_columns()].fillna(0.0)
    y_test = test_df[target_column]

    candidates = _candidate_models()

    results = []

    for model_name, model in candidates.items():
        model.fit(x_train, y_train)

        predictions = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1]

        metrics = {
            "model_name": model_name,
            "accuracy": float(accuracy_score(y_test, predictions)),
            "f1": float(f1_score(y_test, predictions, zero_division=0)),
            "brier_score": float(brier_score_loss(y_test, probabilities)),
            "roc_auc": 0.0,
        }

        try:
            metrics["roc_auc"] = float(roc_auc_score(y_test, probabilities))
        except ValueError:
            metrics["roc_auc"] = 0.0

        results.append(metrics)

    best = sorted(
        results,
        key=lambda item: (
            item["brier_score"],
            -item["roc_auc"],
            -item["f1"],
            -item["accuracy"],
        ),
    )[0]

    return {
        "selected_model": best["model_name"],
        "accuracy": round(best["accuracy"], 4),
        "f1": round(best["f1"], 4),
        "brier_score": round(best["brier_score"], 4),
        "roc_auc": round(best["roc_auc"], 4),
        "candidate_results": [
            {
                "model_name": r["model_name"],
                "accuracy": round(r["accuracy"], 4),
                "f1": round(r["f1"], 4),
                "brier_score": round(r["brier_score"], 4),
                "roc_auc": round(r["roc_auc"], 4),
            }
            for r in results
        ],
    }


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
            n_estimators=250,
            max_depth=12,
            min_samples_split=4,
            min_samples_leaf=2,
            random_state=42,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=250,
            learning_rate=0.05,
            max_leaf_nodes=31,
            random_state=42,
        ),
    }


def _summarize_windows(windows: list[dict]) -> dict:
    total = len(windows)

    return {
        "windows_tested": total,
        "average_accuracy": round(sum(w["accuracy"] for w in windows) / total, 4),
        "average_f1": round(sum(w["f1"] for w in windows) / total, 4),
        "average_brier_score": round(sum(w["brier_score"] for w in windows) / total, 4),
        "average_roc_auc": round(sum(w["roc_auc"] for w in windows) / total, 4),
        "best_window_accuracy": max(w["accuracy"] for w in windows),
        "worst_window_accuracy": min(w["accuracy"] for w in windows),
    }