# backend/app/backtest/rolling.py

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sqlalchemy.orm import Session

from app.features.football_features import (
    MARKET_TARGETS,
    feature_columns,
    load_training_frame,
)


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

    minimum_required = initial_train_size + test_window_size

    if len(df) < minimum_required:
        raise ValueError(
            f"Need at least {minimum_required} played matches."
        )

    windows = []

    start_test_index = initial_train_size

    while start_test_index + test_window_size <= len(df):
        train_df = df.iloc[:start_test_index].copy()
        test_df = df.iloc[start_test_index:start_test_index + test_window_size].copy()

        if train_df[target_column].nunique() < 2:
            start_test_index += test_window_size
            continue

        if test_df[target_column].nunique() < 2:
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
        raise ValueError("No valid rolling windows created.")

    return {
        "market": market,
        "initial_train_size": initial_train_size,
        "test_window_size": test_window_size,
        "windows": windows,
        "summary": _summarize_windows(windows),
    }


def _evaluate_window(
    train_df,
    test_df,
    target_column: str,
) -> dict:
    x_train = train_df[feature_columns()].fillna(0.0)
    y_train = train_df[target_column]

    x_test = test_df[feature_columns()].fillna(0.0)
    y_test = test_df[target_column]

    candidates = _candidate_models()

    trained_models = {}
    model_results = []

    for model_name, model in candidates.items():
        model.fit(x_train, y_train)

        predictions = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1]

        metrics = _metrics(
            y_true=y_test,
            y_pred=predictions,
            probabilities=probabilities,
        )

        trained_models[model_name] = model

        model_results.append(
            {
                "model_name": model_name,
                **metrics,
            }
        )

    weights = _build_weights_from_brier(model_results)

    ensemble_probabilities = _ensemble_probabilities(
        trained_models=trained_models,
        weights=weights,
        x=x_test,
    )

    ensemble_predictions = (ensemble_probabilities >= 0.5).astype(int)

    ensemble_metrics = _metrics(
        y_true=y_test,
        y_pred=ensemble_predictions,
        probabilities=ensemble_probabilities,
    )

    model_results.append(
        {
            "model_name": "WeightedEnsemble",
            **ensemble_metrics,
        }
    )

    best_model = sorted(
        model_results,
        key=lambda item: (
            item["brier_score"],
            -item["roc_auc"],
            -item["f1"],
            -item["accuracy"],
        ),
    )[0]

    return {
        "selected_model": best_model["model_name"],
        "accuracy": round(best_model["accuracy"], 4),
        "f1": round(best_model["f1"], 4),
        "brier_score": round(best_model["brier_score"], 4),
        "roc_auc": round(best_model["roc_auc"], 4),
        "ensemble_weights": weights,
        "candidate_results": [
            {
                "model_name": result["model_name"],
                "accuracy": round(result["accuracy"], 4),
                "f1": round(result["f1"], 4),
                "brier_score": round(result["brier_score"], 4),
                "roc_auc": round(result["roc_auc"], 4),
            }
            for result in model_results
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


def _metrics(y_true, y_pred, probabilities) -> dict[str, float]:
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "roc_auc": 0.0,
    }

    try:
        metrics["roc_auc"] = float(roc_auc_score(y_true, probabilities))
    except ValueError:
        metrics["roc_auc"] = 0.0

    return metrics


def _build_weights_from_brier(results: list[dict]) -> dict[str, float]:
    inverse_scores = {}

    for result in results:
        score = max(result["brier_score"], 0.0001)
        inverse_scores[result["model_name"]] = 1 / score

    total = sum(inverse_scores.values())

    return {
        model_name: round(score / total, 4)
        for model_name, score in inverse_scores.items()
    }


def _ensemble_probabilities(
    trained_models: dict,
    weights: dict[str, float],
    x,
):
    final_probability = None

    for model_name, model in trained_models.items():
        probability = model.predict_proba(x)[:, 1]

        weighted_probability = probability * weights[model_name]

        if final_probability is None:
            final_probability = weighted_probability
        else:
            final_probability += weighted_probability

    return final_probability


def _summarize_windows(windows: list[dict]) -> dict:
    total = len(windows)

    return {
        "windows_tested": total,

        "average_accuracy": round(
            sum(w["accuracy"] for w in windows) / total,
            4,
        ),

        "average_f1": round(
            sum(w["f1"] for w in windows) / total,
            4,
        ),

        "average_brier_score": round(
            sum(w["brier_score"] for w in windows) / total,
            4,
        ),

        "average_roc_auc": round(
            sum(w["roc_auc"] for w in windows) / total,
            4,
        ),

        "best_window_accuracy": max(
            w["accuracy"] for w in windows
        ),

        "worst_window_accuracy": min(
            w["accuracy"] for w in windows
        ),
    }