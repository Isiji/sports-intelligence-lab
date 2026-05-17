# backend/app/ml/predict_football.py

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.features.football_features import (
    MARKET_TARGETS,
    load_upcoming_frame,
)
from app.intelligence.odds_economics import evaluate_odds_economics
from app.ml.market_prediction_resolver import resolve_market_prediction
from app.ml.train_football import model_path_for_market
from app.odds.odds_matcher import find_best_odds_for_prediction
from app.services.production_validation_service import (
    validate_prediction_for_production,
)


def predict_all_football_markets(
    session: Session,
    slate: str = "demo",
    limit: int = 16,
    min_confidence: float = 0.55,
    require_odds: bool = True,
) -> int:
    upcoming_df = load_upcoming_frame(session=session, limit=limit)

    if upcoming_df.empty:
        return 0

    saved = 0

    for market in MARKET_TARGETS.keys():
        model_path = model_path_for_market(market)

        if not model_path.exists():
            print(f"[SKIPPED] {market}: model artifact missing at {model_path}")
            continue

        try:
            bundle = _load_model_bundle(model_path)
        except Exception as exc:
            print(f"[SKIPPED] {market}: failed to load model bundle: {exc}")
            continue

        feature_columns = bundle.get("feature_columns", [])

        if not feature_columns:
            print(f"[SKIPPED] {market}: bundle has no feature_columns")
            continue

        missing_features = [
            column for column in feature_columns
            if column not in upcoming_df.columns
        ]

        if missing_features:
            print(f"[SKIPPED] {market}: missing features: {missing_features[:8]}")
            continue

        x = upcoming_df[feature_columns].fillna(0.0)

        try:
            probabilities = _predict_probabilities(bundle=bundle, x=x)
        except Exception as exc:
            print(f"[SKIPPED] {market}: prediction failed: {exc}")
            continue

        for row_index, row in upcoming_df.iterrows():
            probability = float(probabilities[row_index])

            resolved_prediction = resolve_market_prediction(
                market=market,
                probability=probability,
            )

            if not resolved_prediction.should_save or not resolved_prediction.predicted_label:
                continue

            predicted_label = resolved_prediction.predicted_label
            confidence = resolved_prediction.confidence

            if confidence < min_confidence:
                continue

            odds_payload = _resolve_prediction_odds(
                session=session,
                match_id=int(row["match_id"]),
                market=market,
                predicted_label=predicted_label,
                home_team=str(row["home_team"]),
                away_team=str(row["away_team"]),
            )

            if require_odds and odds_payload["odds"] is None:
                continue

            implied_probability = None
            value_score = None

            if odds_payload["odds"] is not None and odds_payload["odds"] > 0:
                implied_probability = round(1 / odds_payload["odds"], 6)
                value_score = round(confidence - implied_probability, 6)

            economics = evaluate_odds_economics(
                odds=odds_payload["odds"],
                confidence=confidence,
                value_score=value_score,
                production_mode=True,
            )

            if require_odds and not economics.allowed:
                continue

            production_validation = validate_prediction_for_production(
                market=market,
                predicted_label=predicted_label,
                odds_payload=odds_payload,
                odds=odds_payload["odds"],
                confidence=confidence,
                value_score=value_score,
            )

            if not production_validation.allowed:
                continue

            prediction_payload = {
                "slate": slate,
                "match_id": int(row["match_id"]),
                "sport": "football",
                "model_name": bundle.get("selected_model_name", "UnknownModel"),
                "market": market,
                "predicted_label": predicted_label,
                "confidence": round(confidence, 6),
                "odds": odds_payload["odds"],
                "implied_probability": implied_probability,
                "value_score": value_score,
                "odds_bookmaker": odds_payload["odds_bookmaker"],
                "odds_market": odds_payload["odds_market"],
                "odds_selection": odds_payload["odds_selection"],
                "odds_retrieved_at": odds_payload["odds_retrieved_at"],
                "odds_match_quality": odds_payload["odds_match_quality"],
            }

            _upsert_prediction(session=session, payload=prediction_payload)
            saved += 1

    session.commit()
    return saved


def _upsert_prediction(session: Session, payload: dict[str, Any]) -> None:
    stmt = pg_insert(Prediction).values(**payload)

    update_fields = {
        "sport": stmt.excluded.sport,
        "model_name": stmt.excluded.model_name,
        "confidence": stmt.excluded.confidence,
        "odds": stmt.excluded.odds,
        "implied_probability": stmt.excluded.implied_probability,
        "value_score": stmt.excluded.value_score,
        "odds_bookmaker": stmt.excluded.odds_bookmaker,
        "odds_market": stmt.excluded.odds_market,
        "odds_selection": stmt.excluded.odds_selection,
        "odds_retrieved_at": stmt.excluded.odds_retrieved_at,
        "odds_match_quality": stmt.excluded.odds_match_quality,
    }

    stmt = stmt.on_conflict_do_update(
        constraint="uq_prediction_unique_pick",
        set_=update_fields,
    )

    session.execute(stmt)


def _load_model_bundle(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        bundle = pickle.load(file)

    if not isinstance(bundle, dict):
        raise ValueError("model bundle is not a dictionary")

    return bundle


def _predict_probabilities(bundle: dict[str, Any], x) -> list[float]:
    models = bundle.get("models") or {}
    weights = bundle.get("weights") or {}

    if not models:
        raise ValueError("no models found in bundle")

    final_probability = None

    for model_name, model in models.items():
        model_probability = model.predict_proba(x)[:, 1]
        weight = float(weights.get(model_name, 1.0 / max(len(models), 1)))
        weighted_probability = model_probability * weight

        if final_probability is None:
            final_probability = weighted_probability
        else:
            final_probability += weighted_probability

    if final_probability is None:
        raise ValueError("probability calculation failed")

    return [float(value) for value in final_probability]


def _resolve_prediction_odds(
    session: Session,
    match_id: int,
    market: str,
    predicted_label: str,
    home_team: str,
    away_team: str,
) -> dict[str, Any]:
    default_payload = {
        "odds": None,
        "odds_bookmaker": None,
        "odds_market": None,
        "odds_selection": None,
        "odds_retrieved_at": None,
        "odds_match_quality": None,
    }

    try:
        result = find_best_odds_for_prediction(
            session=session,
            match_id=match_id,
            target_market=market,
            predicted_label=predicted_label,
            home_team=home_team,
            away_team=away_team,
        )
    except TypeError:
        result = find_best_odds_for_prediction(
            session=session,
            match_id=match_id,
            target_market=market,
            home_team=home_team,
            away_team=away_team,
        )
    except Exception:
        return default_payload

    if result is None:
        return default_payload

    if isinstance(result, dict):
        return {
            "odds": _safe_float(
                result.get("odds")
                or result.get("price")
                or result.get("decimal_odds")
            ),
            "odds_bookmaker": result.get("bookmaker") or result.get("odds_bookmaker"),
            "odds_market": (
                result.get("odds_market")
                or result.get("executable_market")
                or result.get("market")
                or result.get("raw_market")
            ),
            "odds_selection": (
                result.get("odds_selection")
                or result.get("executable_selection")
                or result.get("selection")
                or result.get("raw_selection")
            ),
            "odds_retrieved_at": result.get("retrieved_at") or result.get("odds_retrieved_at"),
            "odds_match_quality": (
                result.get("match_quality")
                or result.get("odds_match_quality")
                or result.get("reason")
            ),
        }

    return {
        "odds": _safe_float(getattr(result, "odds", None)),
        "odds_bookmaker": getattr(result, "bookmaker", None),
        "odds_market": getattr(result, "odds_market", None) or getattr(result, "market", None),
        "odds_selection": getattr(result, "odds_selection", None) or getattr(result, "selection", None),
        "odds_retrieved_at": getattr(result, "retrieved_at", None),
        "odds_match_quality": getattr(result, "match_quality", None),
    }

def predict_football_market(
    session: Session,
    market: str,
    slate: str = "demo",
    limit: int = 16,
    min_confidence: float = 0.55,
    require_odds: bool = True,
) -> int:
    return predict_all_football_markets(
        session=session,
        slate=slate,
        limit=limit,
        min_confidence=min_confidence,
        require_odds=require_odds,
    )

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None