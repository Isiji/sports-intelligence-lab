# backend/app/ml/predict_football.py

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Match, Prediction
from app.features.football_features import (
    MARKET_TARGETS,
    load_upcoming_frame,
)
from app.intelligence.odds_economics import evaluate_odds_economics
from app.ml.market_prediction_resolver import resolve_market_prediction
from app.ml.train_football import model_path_for_market
from app.odds.executable_market_registry import (
    is_production_ready_market,
    parse_executable_market,
)
from app.services.odds_lookup_service import (
    find_best_odds_for_prediction,
)
from app.services.odds_survivability_service import (
    evaluate_odds_survivability,
)
from app.services.prediction_intelligence_service import (
    apply_prediction_intelligence,
)
from app.services.prediction_market_timing_service import (
    analyze_prediction_timing,
)
from app.services.prediction_alternative_service import (
    build_prediction_alternatives,
)
from app.services.production_validation_service import (
    validate_prediction_for_production,
)

RESEARCH_ONLY_FAMILIES = {
    "EXACT_SCORE",
    "FIRST_HALF_EXACT_SCORE",
}

CONTROLLED_DERIVATIVE_FAMILIES = {
    "HT_FT",
    "HANDICAP_RESULT",
    "RESULT_TOTAL",
}

def predict_all_football_markets(
    session: Session,
    slate: str = "demo",
    limit: int = 16,
    min_confidence: float = 0.55,
    require_odds: bool = True,
) -> int:

    upcoming_df = load_upcoming_frame(
        session=session,
        limit=limit,
    )

    if upcoming_df.empty:
        return 0

    saved = 0

    for market in MARKET_TARGETS.keys():

        if not is_production_ready_market(
            market
        ):
            print(
                f"[SKIPPED] {market}: market not production ready"
            )
            continue

        parsed_market = parse_executable_market(
            market
        )

        if parsed_market.volatility_tier == "EXTREME":
            print(
                f"[SKIPPED] {market}: extreme volatility market"
            )
            continue

        if parsed_market.family in RESEARCH_ONLY_FAMILIES:
            print(
                f"[SKIPPED] {market}: research-only derivative market"
            )
            continue

        if (
            parsed_market.family
            in CONTROLLED_DERIVATIVE_FAMILIES
        ):

            if parsed_market.volatility_tier in {
                "EXTREME",
                "VERY_HIGH",
            }:
                print(
                    f"[SKIPPED] {market}: derivative volatility too high"
                )
                continue

        model_path = model_path_for_market(
            market
        )

        if not model_path.exists():
            print(
                f"[SKIPPED] {market}: model artifact missing at {model_path}"
            )
            continue

        try:
            bundle = _load_model_bundle(
                model_path
            )

        except Exception as exc:
            print(
                f"[SKIPPED] {market}: failed to load model bundle: {exc}"
            )
            continue

        feature_columns = bundle.get(
            "feature_columns",
            [],
        )

        if not feature_columns:
            print(
                f"[SKIPPED] {market}: bundle has no feature_columns"
            )
            continue

        missing_features = [
            column
            for column in feature_columns
            if column not in upcoming_df.columns
        ]

        if missing_features:
            print(
                f"[SKIPPED] {market}: missing features: {missing_features[:8]}"
            )
            continue

        x = upcoming_df[
            feature_columns
        ].fillna(0.0)

        try:
            probabilities = _predict_probabilities(
                bundle=bundle,
                x=x,
            )

        except Exception as exc:
            print(
                f"[SKIPPED] {market}: prediction failed: {exc}"
            )
            continue

        for row_index, row in upcoming_df.iterrows():

            match_id = int(
                row["match_id"]
            )

            timing = analyze_prediction_timing(
                kickoff_value=(
                    row.get("kickoff_datetime")
                    or row.get("kickoff_date")
                )
            )

            if timing.recommended_action == "AVOID":
                continue

            if (
                timing.minutes_to_kickoff is not None
                and timing.minutes_to_kickoff <= 8
            ):
                continue

            if (
                parsed_market.family == "ASIAN_HANDICAP"
                and timing.minutes_to_kickoff is not None
                and timing.minutes_to_kickoff <= 35
            ):
                continue

            probability = float(
                probabilities[row_index]
            )

            resolved_prediction = resolve_market_prediction(
                market=market,
                probability=probability,
            )

            if (
                not resolved_prediction.should_save
                or not resolved_prediction.predicted_label
            ):
                continue

            predicted_label = (
                resolved_prediction.predicted_label
            )

            confidence = float(
                resolved_prediction.confidence
            )

            if confidence < min_confidence:
                continue

            if (
                parsed_market.family == "RESULT_TOTAL"
                and confidence < 0.62
            ):
                continue

            if (
                parsed_market.family == "HANDICAP_RESULT"
                and confidence < 0.60
            ):
                continue

            odds_payload = _resolve_prediction_odds(
                session=session,
                match_id=match_id,
                market=market,
                predicted_label=predicted_label,
                home_team=str(row["home_team"]),
                away_team=str(row["away_team"]),
            )

            if (
                require_odds
                and odds_payload["odds"] is None
            ):
                continue

            survivability = evaluate_odds_survivability(
                market=(
                    odds_payload.get("execution_market")
                    or market
                ),
                bookmaker=odds_payload.get(
                    "odds_bookmaker"
                ),
                odds_retrieved_at=odds_payload.get(
                    "odds_retrieved_at"
                ),
                minutes_to_kickoff=(
                    timing.minutes_to_kickoff
                ),
            )

            if require_odds:

                if (
                    parsed_market.family == "RESULT_TOTAL"
                    and odds_payload["odds"] is not None
                    and float(odds_payload["odds"]) >= 4.50
                ):
                    continue

                if (
                    parsed_market.family == "HANDICAP_RESULT"
                    and odds_payload["odds"] is not None
                    and float(odds_payload["odds"]) >= 4.00
                ):
                    continue

                if not survivability.allowed:
                    continue

                if survivability.stale:
                    continue

                if (
                    survivability.survivability_score
                    < 0.45
                ):
                    continue

            if (
                parsed_market.family == "ASIAN_HANDICAP"
                and odds_payload["odds"] is not None
                and float(odds_payload["odds"]) >= 3.50
            ):
                continue

            implied_probability = None
            value_score = None

            if (
                odds_payload["odds"] is not None
                and odds_payload["odds"] > 0
            ):
                implied_probability = round(
                    1 / odds_payload["odds"],
                    6,
                )

                value_score = round(
                    confidence - implied_probability,
                    6,
                )

            economics = evaluate_odds_economics(
                odds=odds_payload["odds"],
                confidence=confidence,
                value_score=value_score,
                market=(
                    odds_payload.get("execution_market")
                    or market
                ),
                production_mode=True,
            )

            if (
                require_odds
                and not economics.allowed
            ):
                continue

            match_object = session.get(
                Match,
                match_id,
            )

            if not match_object:
                continue

            if getattr(match_object, "is_finished", False):
                continue

            if getattr(match_object, "is_postponed", False):
                continue

            if getattr(match_object, "is_cancelled", False):
                continue

            status = str(
                getattr(match_object, "status", "") or ""
            ).upper()

            if status in {
                "FT",
                "AET",
                "PEN",
                "LIVE",
                "1H",
                "2H",
                "HT",
                "BREAK",
                "INT",
                "PST",
                "CANC",
                "ABD",
            }:
                continue

            intelligence = apply_prediction_intelligence(
                session=session,
                match=match_object,
                market=market,
                raw_confidence=confidence,
                odds=odds_payload["odds"],
                bookmaker=odds_payload["odds_bookmaker"],
            )

            if not intelligence["allowed"]:
                continue

            confidence = float(
                intelligence["adjusted_confidence"]
            )

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

            if (
                parsed_market.family == "RESULT_TOTAL"
                and value_score is not None
                and value_score < 0.035
            ):
                continue

            if (
                parsed_market.family == "HANDICAP_RESULT"
                and value_score is not None
                and value_score < 0.03
            ):
                continue

            execution_score = _safe_float(
                odds_payload.get("execution_score")
            )

            local_realism_score = _safe_float(
                odds_payload.get("local_realism_score")
            )

            survivability_score = _safe_float(
                getattr(
                    survivability,
                    "survivability_score",
                    None,
                )
            )

            execution_ready = (
                odds_payload["odds"] is not None
                and not survivability.stale
                and survivability_score is not None
                and survivability_score >= 0.45
                and (
                    parsed_market.family
                    not in {
                        "RESULT_TOTAL",
                        "HANDICAP_RESULT",
                    }
                    or confidence >= 0.64
                )
                and (
                    execution_score is None
                    or execution_score >= 55.0
                )
            )

            prediction_payload = {
                "slate": slate,
                "match_id": match_id,
                "sport": "football",
                "model_name": bundle.get(
                    "selected_model_name",
                    "UnknownModel",
                ),
                "market": market,
                "predicted_label": predicted_label,
                "confidence": round(
                    confidence,
                    6,
                ),
                "odds": odds_payload["odds"],
                "implied_probability": implied_probability,
                "value_score": value_score,

                "odds_bookmaker": odds_payload["odds_bookmaker"],
                "odds_market": odds_payload["odds_market"],
                "odds_selection": odds_payload["odds_selection"],
                "odds_retrieved_at": odds_payload["odds_retrieved_at"],
                "odds_match_quality": odds_payload["odds_match_quality"],

                "execution_market": odds_payload.get(
                    "execution_market"
                ),
                "execution_selection": odds_payload.get(
                    "execution_selection"
                ),
                "execution_family": odds_payload.get(
                    "execution_family"
                ),
                "execution_line": odds_payload.get(
                    "execution_line"
                ),
                "bookmaker_locality": odds_payload.get(
                    "bookmaker_locality"
                ),
                "local_realism_score": local_realism_score,
                "execution_score": execution_score,
                "survivability_score": survivability_score,
                "execution_ready": execution_ready,
                "execution_reasons": odds_payload.get(
                    "execution_reasons"
                )
                or [],
                "market_alternatives": build_prediction_alternatives(
                    session=session,
                    match_id=match_id,
                    target_market=market,
                    predicted_label=predicted_label,
                    confidence=confidence,
                    value_score=value_score,
                ),
            }

            _upsert_prediction(
                session=session,
                payload=prediction_payload,
            )

            saved += 1

    session.commit()

    return saved


def _upsert_prediction(
    session: Session,
    payload: dict[str, Any],
) -> None:

    stmt = pg_insert(
        Prediction
    ).values(**payload)

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

        "execution_market": stmt.excluded.execution_market,
        "execution_selection": stmt.excluded.execution_selection,
        "execution_family": stmt.excluded.execution_family,
        "execution_line": stmt.excluded.execution_line,
        "bookmaker_locality": stmt.excluded.bookmaker_locality,
        "local_realism_score": stmt.excluded.local_realism_score,
        "execution_score": stmt.excluded.execution_score,
        "survivability_score": stmt.excluded.survivability_score,
        "execution_ready": stmt.excluded.execution_ready,
        "execution_reasons": stmt.excluded.execution_reasons,
        "market_alternatives": stmt.excluded.market_alternatives,
    }

    stmt = stmt.on_conflict_do_update(
        constraint="uq_prediction_unique_pick",
        set_=update_fields,
    )

    session.execute(stmt)


def _load_model_bundle(
    path: Path,
) -> dict[str, Any]:

    with path.open("rb") as file:
        bundle = pickle.load(file)

    if not isinstance(bundle, dict):
        raise ValueError(
            "model bundle is not a dictionary"
        )

    return bundle


def _predict_probabilities(
    bundle: dict[str, Any],
    x,
) -> list[float]:

    models = bundle.get("models") or {}

    weights = bundle.get("weights") or {}

    if not models:
        raise ValueError(
            "no models found in bundle"
        )

    final_probability = None

    for model_name, model in models.items():

        model_probability = (
            model.predict_proba(x)[:, 1]
        )

        weight = float(
            weights.get(
                model_name,
                1.0 / max(len(models), 1),
            )
        )

        weighted_probability = (
            model_probability * weight
        )

        if final_probability is None:
            final_probability = weighted_probability

        else:
            final_probability += weighted_probability

    if final_probability is None:
        raise ValueError(
            "probability calculation failed"
        )

    return [
        float(value)
        for value in final_probability
    ]


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

        "execution_market": None,
        "execution_selection": None,
        "execution_family": None,
        "execution_line": None,
        "bookmaker_locality": None,
        "local_realism_score": None,
        "execution_score": None,
        "execution_reasons": [],
        "market_alternatives": [],
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
            predicted_label=predicted_label,
        )

    except Exception as exc:
        print(
            f"[ODDS_LOOKUP_FAILED] match_id={match_id} market={market}: {exc}"
        )
        return default_payload

    if result is None:
        return default_payload

    if isinstance(result, dict):

        odds = _safe_float(
            result.get("odds")
            or result.get("price")
            or result.get("decimal_odds")
        )

        return {
            "odds": odds,
            "odds_bookmaker": (
                result.get("bookmaker")
                or result.get("odds_bookmaker")
            ),
            "odds_market": (
                result.get("odds_market")
                or result.get("market")
                or result.get("raw_market")
            ),
            "odds_selection": (
                result.get("odds_selection")
                or result.get("selection")
                or result.get("raw_selection")
            ),
            "odds_retrieved_at": (
                result.get("retrieved_at")
                or result.get("odds_retrieved_at")
            ),
            "odds_match_quality": (
                result.get("match_quality")
                or result.get("odds_match_quality")
                or result.get("reason")
            ),

            "execution_market": (
                result.get("execution_market")
                or result.get("executable_market")
            ),
            "execution_selection": (
                result.get("execution_selection")
                or result.get("executable_selection")
            ),
            "execution_family": result.get(
                "execution_family"
            ),
            "execution_line": _safe_float(
                result.get("execution_line")
            ),
            "bookmaker_locality": result.get(
                "bookmaker_locality"
            ),
            "local_realism_score": _safe_float(
                result.get("local_realism_score")
            ),
            "execution_score": _safe_float(
                result.get("execution_score")
            ),
            "execution_reasons": (
                result.get("execution_reasons")
                or []
            ),
            "market_alternatives": (
                result.get("market_alternatives")
                or []
            ),
        }

    return {
        "odds": _safe_float(
            getattr(result, "odds", None)
        ),
        "odds_bookmaker": getattr(
            result,
            "bookmaker",
            None,
        ),
        "odds_market": getattr(
            result,
            "provider_market",
            None,
        ),
        "odds_selection": getattr(
            result,
            "provider_selection",
            None,
        ),
        "odds_retrieved_at": getattr(
            result,
            "retrieved_at",
            None,
        ),
        "odds_match_quality": getattr(
            result,
            "match_quality",
            None,
        ),
        "execution_market": getattr(
            result,
            "executable_market",
            None,
        ),
        "execution_selection": getattr(
            result,
            "executable_selection",
            None,
        ),
        "execution_family": getattr(
            result,
            "execution_family",
            None,
        ),
        "execution_line": _safe_float(
            getattr(
                result,
                "execution_line",
                None,
            )
        ),
        "bookmaker_locality": getattr(
            result,
            "bookmaker_locality",
            None,
        ),
        "local_realism_score": _safe_float(
            getattr(
                result,
                "local_realism_score",
                None,
            )
        ),
        "execution_score": _safe_float(
            getattr(
                result,
                "execution_score",
                None,
            )
        ),
        "execution_reasons": (
            getattr(
                result,
                "execution_reasons",
                None,
            )
            or []
        ),
        "market_alternatives": (
            getattr(
                result,
                "market_alternatives",
                None,
            )
            or []
        ),
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


def _safe_float(
    value: Any,
) -> float | None:

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None