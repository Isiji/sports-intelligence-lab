# backend/app/backtest/thresholds.py

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sqlalchemy.orm import Session

from app.features.football_features import (
    MARKET_TARGETS,
    feature_columns,
    load_training_frame,
)


THRESHOLDS = [
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
]


def optimize_market_thresholds(
    session: Session,
    market: str = "home_win",
) -> dict:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    if market not in MARKET_TARGETS:
        raise ValueError(f"Unsupported market: {market}")

    target_column = MARKET_TARGETS[market]

    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    split_index = int(len(df) * 0.8)

    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    x_train = train_df[feature_columns()].fillna(0.0)
    y_train = train_df[target_column]

    x_test = test_df[feature_columns()].fillna(0.0)
    y_test = test_df[target_column]

    models = _candidate_models()

    trained_models = {}

    for model_name, model in models.items():
        model.fit(x_train, y_train)
        trained_models[model_name] = model

    weights = _build_weights(trained_models, x_test, y_test)

    ensemble_probabilities = _ensemble_probabilities(
        trained_models=trained_models,
        weights=weights,
        x=x_test,
    )

    threshold_results = []

    for threshold in THRESHOLDS:
        filtered = []

        for idx, probability in enumerate(ensemble_probabilities):
            confidence = max(probability, 1 - probability)

            if confidence < threshold:
                continue

            predicted = 1 if probability >= 0.5 else 0

            filtered.append(
                (
                    predicted,
                    int(y_test.iloc[idx]),
                    confidence,
                )
            )

        if not filtered:
            continue

        predictions = [x[0] for x in filtered]
        actuals = [x[1] for x in filtered]
        confidences = [x[2] for x in filtered]

        accuracy = accuracy_score(actuals, predictions)
        f1 = f1_score(actuals, predictions, zero_division=0)

        threshold_results.append(
            {
                "threshold": threshold,
                "predictions_kept": len(filtered),
                "coverage": round(len(filtered) / len(y_test), 4),
                "accuracy": round(float(accuracy), 4),
                "f1": round(float(f1), 4),
                "average_confidence": round(
                    float(sum(confidences) / len(confidences)),
                    4,
                ),
            }
        )

    best_threshold = sorted(
        threshold_results,
        key=lambda item: (
            -item["accuracy"],
            -item["f1"],
            item["coverage"] * -1,
        ),
    )[0]

    return {
        "market": market,
        "recommended_threshold": best_threshold["threshold"],
        "recommended_accuracy": best_threshold["accuracy"],
        "recommended_f1": best_threshold["f1"],
        "recommended_coverage": best_threshold["coverage"],
        "all_thresholds": threshold_results,
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


def _build_weights(trained_models, x_test, y_test):
    scores = {}

    for model_name, model in trained_models.items():
        probabilities = model.predict_proba(x_test)[:, 1]

        predictions = (probabilities >= 0.5).astype(int)

        accuracy = accuracy_score(y_test, predictions)

        scores[model_name] = max(float(accuracy), 0.0001)

    total = sum(scores.values())

    return {
        model_name: round(score / total, 4)
        for model_name, score in scores.items()
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