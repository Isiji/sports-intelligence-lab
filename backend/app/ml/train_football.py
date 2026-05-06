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
    return ARTIFACT_DIR / f"football_{market}_ensemble.pkl"


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
        try:
            _train_market_model(
                session=session,
                df=df,
                market=market,
                target_column=target_column,
            )
        except ValueError as exc:
            print(f"[SKIPPED] {market}: {exc}")


def _train_market_model(session: Session, df, market: str, target_column: str) -> None:
    if target_column not in df.columns:
        raise ValueError("target column missing.")

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

    trained_models = {}
    candidate_results = []

    for model_name, model in candidates.items():
        model.fit(x_train, y_train)

        predictions = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1]

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
                train_size=len(train_df),
                test_size=len(test_df),
                selected=1 if result["model_name"] == selected_result["model_name"] else 0,
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
            train_size=len(train_df),
            test_size=len(test_df),
            selected=1 if selected_result["model_name"] == "WeightedEnsemble" else 0,
        )
    )

    session.commit()

    if selected_result["model_name"] == "WeightedEnsemble":
        saved_models = trained_models
        saved_weights = ensemble_weights
    else:
        saved_models = {
            selected_result["model_name"]: trained_models[selected_result["model_name"]]
        }
        saved_weights = {
            selected_result["model_name"]: 1.0
        }

    save_path = model_path_for_market(market)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    bundle = {
        "market": market,
        "selected_model_name": selected_result["model_name"],
        "models": saved_models,
        "weights": saved_weights,
        "feature_columns": feature_columns(),
    }

    with save_path.open("wb") as file:
        pickle.dump(bundle, file)

    save_model_metadata(
        metadata_path=metadata_path_for_market(market),
        market=market,
        selected_model_name=selected_result["model_name"],
        selected_accuracy=selected_result["accuracy"],
        feature_columns=feature_columns(),
        extra={
            "selection_rule": "lowest_brier_then_highest_roc_auc_f1_accuracy",
            "weights": saved_weights,
            "precision": round(selected_result["precision"], 4),
            "recall": round(selected_result["recall"], 4),
            "f1": round(selected_result["f1"], 4),
            "log_loss": round(selected_result["log_loss"], 4),
            "brier_score": round(selected_result["brier_score"], 4),
            "roc_auc": round(selected_result["roc_auc"], 4),
            "train_size": len(train_df),
            "test_size": len(test_df),
            "split_type": "chronological_80_20",
            "train_start": str(train_df["kickoff_date"].min()),
            "train_end": str(train_df["kickoff_date"].max()),
            "test_start": str(test_df["kickoff_date"].min()),
            "test_end": str(test_df["kickoff_date"].max()),
        },
    )

    print(f"\n[{market}] Model comparison:")

    for result in all_results:
        print(
            f"{result['model_name']}: "
            f"accuracy={round(result['accuracy'], 4)}, "
            f"f1={round(result['f1'], 4)}, "
            f"brier={round(result['brier_score'], 4)}, "
            f"roc_auc={round(result['roc_auc'], 4)}"
        )

    print(f"Selected: {selected_result['model_name']}")
    print(f"Saved weights: {saved_weights}\n")


def _chronological_split(df):
    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    if len(df) < 50:
        raise ValueError("Need at least 50 played matches.")

    split_index = int(len(df) * 0.8)

    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    if train_df.empty or test_df.empty:
        raise ValueError("Empty train/test split.")

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
        model_probability = model.predict_proba(x)[:, 1]
        weighted_probability = model_probability * weights[model_name]

        if final_probability is None:
            final_probability = weighted_probability
        else:
            final_probability += weighted_probability

    return final_probability