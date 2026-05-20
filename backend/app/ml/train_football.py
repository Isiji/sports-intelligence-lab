# backend/app/ml/train_football.py

from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

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
    filter_training_frame_for_market,
    load_training_frame,
)
from app.features.market_feature_map import feature_columns_for_market
from app.ml.registry import save_model_metadata


ARTIFACT_DIR = Path("artifacts")

MIN_TOTAL_ROWS = 120
MIN_TRAIN_ROWS = 80
MIN_TEST_ROWS = 30
MIN_CLASS_RATE = 0.04
MAX_CLASS_RATE = 0.96

MAX_BRIER_DEGRADATION_RATIO = 1.08
MAX_BRIER_DEGRADATION_ABSOLUTE = 0.025


STRICT_MARKETS = {
    "draw",
    "under_1_5_goals",
    "over_3_5_goals",
    "home_win_to_nil",
    "away_win_to_nil",
    "asian_handicap_home_minus_1_5",
    "asian_handicap_away_minus_1_5",
}


def model_path_for_market(market: str) -> Path:
    return ARTIFACT_DIR / f"football_{market}_ensemble.pkl"


def challenger_model_path_for_market(market: str) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return ARTIFACT_DIR / "challengers" / f"football_{market}_{timestamp}.pkl"


def metadata_path_for_market(market: str) -> Path:
    return ARTIFACT_DIR / f"football_{market}_model.json"


def train_all_football_models(session: Session) -> None:
    df = load_training_frame(session)

    if df.empty:
        raise ValueError("No training data found.")

    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    print(f"\nTraining frame loaded: {len(df)} finished matches")
    print(f"Date range: {df['kickoff_date'].min()} → {df['kickoff_date'].max()}")

    trained = 0
    skipped = 0
    protected = 0

    for market, target_column in MARKET_TARGETS.items():
        try:
            market_df = filter_training_frame_for_market(df, market)

            print(f"\n[{market}] usable rows after market filtering: {len(market_df)}")

            result = _train_market_model(
                session=session,
                df=market_df,
                market=market,
                target_column=target_column,
            )

            if result["promoted"]:
                trained += 1
            else:
                protected += 1

        except ValueError as exc:
            skipped += 1
            print(f"[SKIPPED] {market}: {exc}")

    print(
        "\n=== TRAINING SUMMARY ===\n"
        f"promoted_models={trained}\n"
        f"protected_existing_models={protected}\n"
        f"skipped_markets={skipped}\n"
    )


def _train_market_model(
    session: Session,
    df,
    market: str,
    target_column: str,
) -> dict[str, Any]:
    _validate_training_frame(df=df, market=market, target_column=target_column)

    train_df, test_df = _chronological_split(df)

    _validate_split(
        train_df=train_df,
        test_df=test_df,
        target_column=target_column,
    )

    market_features = feature_columns_for_market(market)

    if not market_features:
        raise ValueError("no feature columns resolved for market.")

    x_train = train_df[market_features].fillna(0.0)
    y_train = train_df[target_column]

    x_test = test_df[market_features].fillna(0.0)
    y_test = test_df[target_column]

    candidates = _candidate_models(y_train)

    trained_models = {}
    candidate_results = []

    for model_name, model in candidates.items():
        model.fit(x_train, y_train)

        probabilities = _safe_predict_proba(model, x_test)
        predictions = (probabilities >= 0.5).astype(int)

        metrics = _calculate_metrics(
            y_true=y_test,
            y_pred=predictions,
            probabilities=probabilities,
        )

        trained_models[model_name] = model

        candidate_results.append(
            {
                "model_name": model_name,
                "model": model,
                **metrics,
            }
        )

    ensemble_weights = _build_weights_from_brier(candidate_results)

    ensemble_probabilities = _ensemble_probabilities(
        trained_models=trained_models,
        weights=ensemble_weights,
        x=x_test,
    )

    ensemble_predictions = (ensemble_probabilities >= 0.5).astype(int)

    ensemble_metrics = _calculate_metrics(
        y_true=y_test,
        y_pred=ensemble_predictions,
        probabilities=ensemble_probabilities,
    )

    all_results = candidate_results + [
        {
            "model_name": "WeightedEnsemble",
            "model": None,
            **ensemble_metrics,
        }
    ]

    selected_result = _select_best_model(all_results)

    if selected_result["model_name"] == "WeightedEnsemble":
        saved_models = trained_models
        saved_weights = ensemble_weights
    else:
        saved_models = {
            selected_result["model_name"]: trained_models[selected_result["model_name"]]
        }
        saved_weights = {
            selected_result["model_name"]: 1.0,
        }

    bundle = {
        "market": market,
        "selected_model_name": selected_result["model_name"],
        "models": saved_models,
        "weights": saved_weights,
        "feature_columns": market_features,
        "trained_at": datetime.utcnow().isoformat(),
        "training_rows": len(df),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
    }

    old_metadata = _load_existing_metadata(metadata_path_for_market(market))

    health = _model_health_check(
        market=market,
        selected_result=selected_result,
        train_df=train_df,
        test_df=test_df,
        target_column=target_column,
        old_metadata=old_metadata,
    )

    promoted = health["promote"]

    _record_training_runs(
        session=session,
        market=market,
        candidate_results=candidate_results,
        ensemble_metrics=ensemble_metrics,
        selected_result=selected_result,
        train_size=len(train_df),
        test_size=len(test_df),
        promoted=promoted,
    )

    if promoted:
        save_path = model_path_for_market(market)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with save_path.open("wb") as file:
            pickle.dump(bundle, file)

        save_model_metadata(
            metadata_path=metadata_path_for_market(market),
            market=market,
            selected_model_name=selected_result["model_name"],
            selected_accuracy=selected_result["accuracy"],
            feature_columns=market_features,
            extra={
                "training_status": "promoted",
                "selection_rule": "lowest_brier_then_highest_roc_auc_f1_accuracy",
                "promotion_reason": health["reason"],
                "weights": saved_weights,
                "precision": round(selected_result["precision"], 4),
                "recall": round(selected_result["recall"], 4),
                "f1": round(selected_result["f1"], 4),
                "log_loss": round(selected_result["log_loss"], 4),
                "brier_score": round(selected_result["brier_score"], 4),
                "roc_auc": round(selected_result["roc_auc"], 4),
                "positive_rate_train": round(float(train_df[target_column].mean()), 4),
                "positive_rate_test": round(float(test_df[target_column].mean()), 4),
                "train_size": len(train_df),
                "test_size": len(test_df),
                "total_size": len(df),
                "split_type": "chronological_80_20",
                "train_start": str(train_df["kickoff_date"].min()),
                "train_end": str(train_df["kickoff_date"].max()),
                "test_start": str(test_df["kickoff_date"].min()),
                "test_end": str(test_df["kickoff_date"].max()),
                "trained_at": datetime.utcnow().isoformat(),
            },
        )

    else:
        challenger_path = challenger_model_path_for_market(market)
        challenger_path.parent.mkdir(parents=True, exist_ok=True)

        with challenger_path.open("wb") as file:
            pickle.dump(bundle, file)

    _print_market_report(
        market=market,
        all_results=all_results,
        selected_result=selected_result,
        promoted=promoted,
        health=health,
        saved_weights=saved_weights,
    )

    return {
        "market": market,
        "promoted": promoted,
        "reason": health["reason"],
    }


def _validate_training_frame(df, market: str, target_column: str) -> None:
    if df.empty:
        raise ValueError("no usable rows after market filtering.")

    if target_column not in df.columns:
        raise ValueError("target column missing.")

    min_rows = 220 if market in STRICT_MARKETS else MIN_TOTAL_ROWS

    if len(df) < min_rows:
        raise ValueError(f"not enough rows. required={min_rows}, found={len(df)}")

    unique_classes = df[target_column].nunique()

    if unique_classes < 2:
        raise ValueError("target has only one class.")

    positive_rate = float(df[target_column].mean())

    if positive_rate < MIN_CLASS_RATE or positive_rate > MAX_CLASS_RATE:
        raise ValueError(
            f"class imbalance too extreme. positive_rate={round(positive_rate, 4)}"
        )


def _chronological_split(df):
    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    split_index = int(len(df) * 0.8)

    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    if train_df.empty or test_df.empty:
        raise ValueError("Empty train/test split.")

    return train_df, test_df


def _validate_split(train_df, test_df, target_column: str) -> None:
    if len(train_df) < MIN_TRAIN_ROWS:
        raise ValueError(f"training split too small: {len(train_df)}")

    if len(test_df) < MIN_TEST_ROWS:
        raise ValueError(f"testing split too small: {len(test_df)}")

    if train_df[target_column].nunique() < 2:
        raise ValueError("training split has only one class.")

    if test_df[target_column].nunique() < 2:
        raise ValueError("testing split has only one class.")


def _candidate_models(y_train) -> dict[str, object]:
    min_class_count = int(y_train.value_counts().min())
    calibration_cv = min(3, min_class_count)

    if calibration_cv >= 2:
        calibrated_logistic = CalibratedClassifierCV(
            estimator=LogisticRegression(
                max_iter=2500,
                class_weight="balanced",
            ),
            cv=calibration_cv,
            method="sigmoid",
        )
    else:
        calibrated_logistic = LogisticRegression(
            max_iter=2500,
            class_weight="balanced",
        )

    return {
        "LogisticRegression": Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("model", calibrated_logistic),
            ]
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=350,
            max_depth=12,
            min_samples_split=6,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=260,
            learning_rate=0.035,
            max_leaf_nodes=31,
            l2_regularization=0.05,
            random_state=42,
        ),
    }


def _safe_predict_proba(model, x):
    probabilities = model.predict_proba(x)

    if probabilities.shape[1] == 1:
        return probabilities[:, 0]

    return probabilities[:, 1]


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
    return sorted(
        results,
        key=lambda item: (
            item["brier_score"],
            -item["roc_auc"],
            -item["f1"],
            -item["accuracy"],
        ),
    )[0]


def _build_weights_from_brier(results: list[dict]) -> dict[str, float]:
    scores = {}

    for result in results:
        brier = max(result["brier_score"], 0.0001)
        scores[result["model_name"]] = 1 / brier

    total = sum(scores.values())

    return {
        model_name: round(score / total, 4)
        for model_name, score in scores.items()
    }


def _ensemble_probabilities(trained_models: dict, weights: dict[str, float], x):
    final_probability = None

    for model_name, model in trained_models.items():
        model_probability = _safe_predict_proba(model, x)
        weighted_probability = model_probability * weights[model_name]

        if final_probability is None:
            final_probability = weighted_probability
        else:
            final_probability += weighted_probability

    return final_probability


def _load_existing_metadata(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def _extract_old_brier(metadata: dict[str, Any] | None) -> float | None:
    if not metadata:
        return None

    extra = metadata.get("extra") or {}

    value = extra.get("brier_score")

    if value is None:
        value = metadata.get("brier_score")

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _model_health_check(
    market: str,
    selected_result: dict[str, Any],
    train_df,
    test_df,
    target_column: str,
    old_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    new_brier = float(selected_result["brier_score"])
    new_roc_auc = float(selected_result["roc_auc"])
    new_f1 = float(selected_result["f1"])

    if new_brier <= 0 or new_brier >= 0.45:
        return {
            "promote": False,
            "reason": f"rejected: unhealthy brier_score={round(new_brier, 4)}",
        }

    if new_roc_auc < 0.50 and new_f1 < 0.10:
        return {
            "promote": False,
            "reason": "rejected: weak discrimination and weak f1",
        }

    train_rate = float(train_df[target_column].mean())
    test_rate = float(test_df[target_column].mean())

    if abs(train_rate - test_rate) > 0.25:
        return {
            "promote": False,
            "reason": (
                "rejected: train/test target drift too high "
                f"train_rate={round(train_rate, 4)} test_rate={round(test_rate, 4)}"
            ),
        }

    old_brier = _extract_old_brier(old_metadata)

    if old_brier is None:
        return {
            "promote": True,
            "reason": "promoted: no existing champion metadata",
        }

    allowed_brier = max(
        old_brier * MAX_BRIER_DEGRADATION_RATIO,
        old_brier + MAX_BRIER_DEGRADATION_ABSOLUTE,
    )

    if new_brier <= allowed_brier:
        return {
            "promote": True,
            "reason": (
                f"promoted: challenger acceptable "
                f"old_brier={round(old_brier, 4)} new_brier={round(new_brier, 4)}"
            ),
        }

    return {
        "promote": False,
        "reason": (
            f"rejected: challenger worse than champion "
            f"old_brier={round(old_brier, 4)} new_brier={round(new_brier, 4)}"
        ),
    }


def _record_training_runs(
    session: Session,
    market: str,
    candidate_results: list[dict],
    ensemble_metrics: dict[str, float],
    selected_result: dict[str, Any],
    train_size: int,
    test_size: int,
    promoted: bool,
) -> None:
    for result in candidate_results:
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
                train_size=train_size,
                test_size=test_size,
                selected=(
                    1
                    if promoted
                    and result["model_name"] == selected_result["model_name"]
                    else 0
                ),
            )
        )

    session.add(
        ModelTrainingRun(
            sport="football",
            market=market,
            model_name="WeightedEnsemble",
            accuracy=round(ensemble_metrics["accuracy"], 4),
            precision=round(ensemble_metrics["precision"], 4),
            recall=round(ensemble_metrics["recall"], 4),
            f1=round(ensemble_metrics["f1"], 4),
            log_loss=round(ensemble_metrics["log_loss"], 4),
            brier_score=round(ensemble_metrics["brier_score"], 4),
            roc_auc=round(ensemble_metrics["roc_auc"], 4),
            train_size=train_size,
            test_size=test_size,
            selected=(
                1
                if promoted and selected_result["model_name"] == "WeightedEnsemble"
                else 0
            ),
        )
    )

    session.commit()


def _print_market_report(
    market: str,
    all_results: list[dict],
    selected_result: dict[str, Any],
    promoted: bool,
    health: dict[str, Any],
    saved_weights: dict[str, float],
) -> None:
    print(f"\n[{market}] Model comparison:")

    for result in all_results:
        print(
            f"{result['model_name']}: "
            f"accuracy={round(result['accuracy'], 4)}, "
            f"precision={round(result['precision'], 4)}, "
            f"recall={round(result['recall'], 4)}, "
            f"f1={round(result['f1'], 4)}, "
            f"brier={round(result['brier_score'], 4)}, "
            f"roc_auc={round(result['roc_auc'], 4)}"
        )

    print(f"Selected challenger: {selected_result['model_name']}")
    print(f"Promoted to champion: {promoted}")
    print(f"Reason: {health['reason']}")
    print(f"Saved weights: {saved_weights}\n")