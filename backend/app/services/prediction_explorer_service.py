# backend/app/services/prediction_explorer_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app.db.models import Match, MatchOdds, Prediction
from app.features.football_features import load_single_match_frame


EAT_OFFSET_HOURS = 3


@dataclass
class ExplorerFilters:
    team: str | None = None
    league: str | None = None
    market: str | None = None
    slate: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_confidence: float = 0.0
    execution_ready_only: bool = False
    local_only: bool = False
    limit: int = 50
    offset: int = 0
    sort_by: str = "confidence"


# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.80:
        return "VERY_STRONG"
    if confidence >= 0.70:
        return "STRONG"
    if confidence >= 0.60:
        return "MODERATE"
    if confidence >= 0.55:
        return "WEAK"
    return "VERY_WEAK"


def _kickoff_eat(match: Match) -> str | None:
    if not match.kickoff_datetime:
        return None
    return match.kickoff_datetime.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------

def _match_payload(match: Match) -> dict[str, Any]:
    return {
        "match_id": match.id,
        "provider_fixture_id": match.provider_fixture_id,
        "sport": match.sport,
        "league": match.league,
        "season": match.season,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "kickoff_date": str(match.kickoff_date) if match.kickoff_date else None,
        "kickoff_datetime": match.kickoff_datetime.isoformat()
        if match.kickoff_datetime
        else None,
        "kickoff_eat": _kickoff_eat(match),
        "status": match.status,
        "is_finished": match.is_finished,
        "is_postponed": match.is_postponed,
        "is_cancelled": match.is_cancelled,
        "has_stats": match.has_stats,
        "has_odds": match.has_odds,
    }


def _prediction_payload(prediction: Prediction) -> dict[str, Any]:
    return {
        "prediction_id": prediction.id,
        "temporary_analysis": False,
        "source_type": "saved_prediction",
        "slate": prediction.slate,
        "match_id": prediction.match_id,
        "sport": prediction.sport,
        "model_name": prediction.model_name,
        "market": prediction.market,
        "predicted_label": prediction.predicted_label,
        "confidence": _safe_float(prediction.confidence),
        "odds": _safe_float(prediction.odds),
        "implied_probability": _safe_float(prediction.implied_probability),
        "value_score": _safe_float(prediction.value_score),
        "odds_bookmaker": prediction.odds_bookmaker,
        "odds_market": prediction.odds_market,
        "odds_selection": prediction.odds_selection,
        "odds_retrieved_at": prediction.odds_retrieved_at.isoformat()
        if prediction.odds_retrieved_at
        else None,
        "odds_match_quality": prediction.odds_match_quality,
        "execution_market": prediction.execution_market,
        "execution_selection": prediction.execution_selection,
        "execution_family": prediction.execution_family,
        "execution_line": _safe_float(prediction.execution_line),
        "bookmaker_locality": prediction.bookmaker_locality,
        "local_realism_score": _safe_float(prediction.local_realism_score),
        "execution_score": _safe_float(prediction.execution_score),
        "survivability_score": _safe_float(prediction.survivability_score),
        "execution_ready": bool(prediction.execution_ready)
        if prediction.execution_ready is not None
        else False,
        "execution_reasons": prediction.execution_reasons or [],
        "market_alternatives": prediction.market_alternatives or [],
        "settlement": {
            "is_correct": prediction.is_correct,
            "result_label": prediction.result_label,
            "profit_loss": _safe_float(prediction.profit_loss),
            "stake": _safe_float(prediction.stake),
            "settled_at": prediction.settled_at.isoformat()
            if prediction.settled_at
            else None,
            "closing_odds": _safe_float(prediction.closing_odds),
            "clv": _safe_float(prediction.clv),
        },
        "created_at": prediction.created_at.isoformat()
        if prediction.created_at
        else None,
    }


def _build_analysis_reasoning(
    *,
    market: str,
    predicted_label: str,
    confidence: float,
    odds_payload: dict[str, Any],
    execution_market: str,
    execution_gate,
    survivability,
    timing,
) -> dict[str, Any]:
    bookmaker_locality = odds_payload.get("bookmaker_locality")
    local_realism_score = _safe_float(odds_payload.get("local_realism_score"))
    odds = _safe_float(odds_payload.get("odds"))

    if predicted_label.startswith("NOT_"):
        model_view = f"Model is rejecting {market} rather than backing it directly."
    else:
        model_view = f"Model is backing {predicted_label} on {market}."

    risk_flags: list[str] = []

    if bookmaker_locality != "LOCAL":
        risk_flags.append("Odds are from a global bookmaker, not a Kenyan-local source.")

    if local_realism_score is not None and local_realism_score < 0.70:
        risk_flags.append("Local realism score is weak; Kenyan bookmaker availability may differ.")

    if odds is None:
        risk_flags.append("No executable odds found.")
    elif odds < 1.30:
        risk_flags.append("Odds are low; value may be limited.")

    if not execution_gate.grouping_allowed:
        risk_flags.append("Execution intelligence does not allow grouping.")

    if timing.timing_status == "EARLY_PRE_MATCH":
        risk_flags.append("Early pre-match odds can change before kickoff.")

    return {
        "model_view": model_view,
        "execution_view": (
            f"Execution market resolved to {execution_market} "
            f"with selection {odds_payload.get('execution_selection')}."
        ),
        "risk_view": risk_flags,
        "user_action": (
            "Check Kenyan bookmaker availability before using this in a real slip."
            if bookmaker_locality != "LOCAL"
            else "Kenyan-local odds found; still verify price movement before grouping."
        ),
        "confidence_band": _confidence_band(confidence),
        "odds_view": {
            "odds": odds,
            "bookmaker": odds_payload.get("odds_bookmaker"),
            "bookmaker_locality": bookmaker_locality,
            "local_realism_score": local_realism_score,
        },
        "timing_view": {
            "status": timing.timing_status,
            "minutes_to_kickoff": timing.minutes_to_kickoff,
            "recommended_action": timing.recommended_action,
        },
        "execution_view_raw": {
            "verdict": execution_gate.verdict,
            "prediction_allowed": execution_gate.prediction_allowed,
            "grouping_allowed": execution_gate.grouping_allowed,
            "reason": execution_gate.reason,
            "survivability_score": getattr(survivability, "survivability_score", None),
        },
    }


# ---------------------------------------------------------------------
# Search APIs
# ---------------------------------------------------------------------

def search_predictions(session: Session, filters: ExplorerFilters) -> dict[str, Any]:
    stmt = (
        select(Prediction, Match)
        .join(Match, Match.id == Prediction.match_id)
        .where(Prediction.confidence >= filters.min_confidence)
    )

    if filters.team:
        pattern = f"%{filters.team}%"
        stmt = stmt.where(or_(Match.home_team.ilike(pattern), Match.away_team.ilike(pattern)))

    if filters.league:
        stmt = stmt.where(Match.league.ilike(f"%{filters.league}%"))

    if filters.market:
        stmt = stmt.where(Prediction.market == filters.market)

    if filters.slate:
        stmt = stmt.where(Prediction.slate == filters.slate)

    if filters.date_from:
        stmt = stmt.where(Match.kickoff_datetime >= filters.date_from)

    if filters.date_to:
        stmt = stmt.where(Match.kickoff_datetime <= filters.date_to)

    if filters.execution_ready_only:
        stmt = stmt.where(Prediction.execution_ready.is_(True))

    if filters.local_only:
        stmt = stmt.where(Prediction.bookmaker_locality == "LOCAL")

    if filters.sort_by == "execution_score":
        stmt = stmt.order_by(desc(Prediction.execution_score.nullslast()))
    elif filters.sort_by == "survivability":
        stmt = stmt.order_by(desc(Prediction.survivability_score.nullslast()))
    elif filters.sort_by == "value":
        stmt = stmt.order_by(desc(Prediction.value_score.nullslast()))
    else:
        stmt = stmt.order_by(desc(Prediction.confidence))

    rows = session.execute(stmt.offset(filters.offset).limit(filters.limit)).all()

    return {
        "count": len(rows),
        "limit": filters.limit,
        "offset": filters.offset,
        "items": [
            {"match": _match_payload(match), "prediction": _prediction_payload(prediction)}
            for prediction, match in rows
        ],
    }


def search_matches(
    session: Session,
    team: str | None = None,
    league: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    stmt = select(Match)

    if team:
        pattern = f"%{team}%"
        stmt = stmt.where(or_(Match.home_team.ilike(pattern), Match.away_team.ilike(pattern)))

    if league:
        stmt = stmt.where(Match.league.ilike(f"%{league}%"))

    if date_from:
        stmt = stmt.where(Match.kickoff_datetime >= date_from)

    if date_to:
        stmt = stmt.where(Match.kickoff_datetime <= date_to)

    matches = list(session.scalars(stmt.order_by(Match.kickoff_datetime.asc()).limit(limit)))

    return {
        "count": len(matches),
        "items": [_match_payload(match) for match in matches],
    }


def get_match_intelligence(session: Session, match_id: int) -> dict[str, Any]:
    match = session.get(Match, match_id)

    if not match:
        raise ValueError("Match not found.")

    predictions = list(
        session.scalars(
            select(Prediction)
            .where(Prediction.match_id == match_id)
            .order_by(desc(Prediction.confidence))
        )
    )

    odds_rows = list(
        session.scalars(
            select(MatchOdds)
            .where(MatchOdds.match_id == match_id)
            .order_by(MatchOdds.market.asc(), MatchOdds.selection.asc())
        )
    )

    return {
        "match": _match_payload(match),
        "has_saved_predictions": len(predictions) > 0,
        "predictions": [_prediction_payload(p) for p in predictions],
        "odds": [
            {
                "bookmaker": row.bookmaker,
                "provider": row.provider,
                "market": row.market,
                "selection": row.selection,
                "odds": _safe_float(row.odds),
                "retrieved_at": row.retrieved_at.isoformat()
                if row.retrieved_at
                else None,
            }
            for row in odds_rows
        ],
        "available_markets": sorted({row.market for row in odds_rows}),
        "available_bookmakers": sorted({row.bookmaker for row in odds_rows if row.bookmaker}),
    }


# ---------------------------------------------------------------------
# On-demand analysis API
# ---------------------------------------------------------------------

def analyze_match_on_demand(
    session: Session,
    match_id: int,
    market: str,
    save_prediction: bool = False,
) -> dict[str, Any]:
    from app.ml.market_prediction_resolver import resolve_market_prediction
    from app.ml.predict_football import (
        _load_model_bundle,
        _predict_probabilities,
        _resolve_prediction_odds,
    )
    from app.ml.train_football import model_path_for_market
    from app.services.execution_market_intelligence_service import get_execution_market_gate
    from app.services.odds_survivability_service import evaluate_odds_survivability
    from app.services.prediction_market_timing_service import analyze_prediction_timing

    match = session.get(Match, match_id)

    if not match:
        raise ValueError("Match not found.")

    if match.is_finished or match.is_cancelled or match.is_postponed:
        return {
            "temporary_analysis": True,
            "source_type": "blocked_analysis",
            "match": _match_payload(match),
            "selected_market": market,
            "prediction": None,
            "reason": "Match is finished, cancelled, or postponed. Live on-demand analysis blocked.",
        }

    existing_predictions = list(
        session.scalars(
            select(Prediction)
            .where(and_(Prediction.match_id == match_id, Prediction.market == market))
            .order_by(desc(Prediction.confidence))
        )
    )

    if existing_predictions:
        return {
            "temporary_analysis": False,
            "source_type": "saved_prediction",
            "match": _match_payload(match),
            "selected_market": market,
            "predictions": [_prediction_payload(p) for p in existing_predictions],
        }

    model_path = model_path_for_market(market)

    if not model_path.exists():
        raise ValueError(f"Model not found for market: {market}")

    bundle = _load_model_bundle(model_path)
    model_feature_columns = bundle.get("feature_columns", [])

    if not model_feature_columns:
        raise ValueError("Model bundle missing feature columns.")

    target_rows = load_single_match_frame(session=session, match_id=match_id)

    if target_rows.empty:
        return {
            "temporary_analysis": True,
            "source_type": "missing_features",
            "match": _match_payload(match),
            "selected_market": market,
            "prediction": None,
            "reason": "Match features unavailable. Run feature build or ingest/update upcoming fixtures first.",
        }

    missing_features = [col for col in model_feature_columns if col not in target_rows.columns]

    if missing_features:
        raise ValueError(f"Missing features: {missing_features[:8]}")

    row = target_rows.iloc[0]
    x = target_rows[model_feature_columns].fillna(0.0)

    probabilities = _predict_probabilities(bundle=bundle, x=x)
    probability = float(probabilities[0])

    resolved = resolve_market_prediction(market=market, probability=probability)

    if not resolved.should_save:
        return {
            "temporary_analysis": True,
            "source_type": "weak_prediction",
            "match": _match_payload(match),
            "selected_market": market,
            "prediction_allowed": False,
            "prediction": None,
            "reason": "Prediction confidence too weak.",
        }

    predicted_label = resolved.predicted_label
    confidence = float(resolved.confidence)

    timing = analyze_prediction_timing(
        kickoff_value=row.get("kickoff_datetime") or row.get("kickoff_date")
    )

    odds_payload = _resolve_prediction_odds(
        session=session,
        match_id=match_id,
        market=market,
        predicted_label=predicted_label,
        home_team=str(row["home_team"]),
        away_team=str(row["away_team"]),
    )

    execution_market = odds_payload.get("execution_market") or market

    execution_gate = get_execution_market_gate(
        session=session,
        execution_market=execution_market,
        sport="football",
    )

    survivability = evaluate_odds_survivability(
        market=execution_market,
        bookmaker=odds_payload.get("odds_bookmaker"),
        odds_retrieved_at=odds_payload.get("odds_retrieved_at"),
        minutes_to_kickoff=timing.minutes_to_kickoff,
    )

    reasoning = _build_analysis_reasoning(
        market=market,
        predicted_label=predicted_label,
        confidence=confidence,
        odds_payload=odds_payload,
        execution_market=execution_market,
        execution_gate=execution_gate,
        survivability=survivability,
        timing=timing,
    )

    return {
        "temporary_analysis": True,
        "source_type": "temporary_analysis",
        "match": _match_payload(match),
        "selected_market": market,
        "prediction": {
            "market": market,
            "predicted_label": predicted_label,
            "confidence": confidence,
            "odds": odds_payload.get("odds"),
            "execution_market": execution_market,
            "execution_selection": odds_payload.get("execution_selection"),
            "execution_score": odds_payload.get("execution_score"),
            "execution_ready": execution_gate.grouping_allowed,
            "survivability_score": getattr(survivability, "survivability_score", None),
            "bookmaker": odds_payload.get("odds_bookmaker"),
            "bookmaker_locality": odds_payload.get("bookmaker_locality"),
            "local_realism_score": odds_payload.get("local_realism_score"),
        },
        "reasoning": reasoning,
        "timing": {
            "recommended_action": timing.recommended_action,
            "timing_status": timing.timing_status,
            "minutes_to_kickoff": timing.minutes_to_kickoff,
        },
        "execution_market_intelligence": {
            "verdict": execution_gate.verdict,
            "prediction_allowed": execution_gate.prediction_allowed,
            "grouping_allowed": execution_gate.grouping_allowed,
            "survivability_score": execution_gate.survivability_score,
            "reason": execution_gate.reason,
        },
    }

from app.features.football_features import MARKET_TARGETS


CORE_EXPLORER_MARKETS = [
    "home_win",
    "draw",
    "away_win",
    "btts_yes",
    "btts_no",
    "over_1_5_goals",
    "over_2_5_goals",
    "under_2_5_goals",
    "double_chance_1x",
    "double_chance_x2",
    "double_chance_12",
]


def get_market_alternatives(
    session: Session,
    match_id: int,
) -> dict[str, Any]:

    match = session.get(Match, match_id)

    if not match:
        raise ValueError("Match not found.")

    alternatives = []

    for market in CORE_EXPLORER_MARKETS:

        try:
            result = analyze_match_on_demand(
                session=session,
                match_id=match_id,
                market=market,
            )

            prediction = result.get("prediction")

            if not prediction:
                continue

            alternatives.append(
                {
                    "market": market,
                    "predicted_label": prediction.get(
                        "predicted_label"
                    ),
                    "confidence": prediction.get(
                        "confidence"
                    ),
                    "odds": prediction.get(
                        "odds"
                    ),
                    "execution_market": prediction.get(
                        "execution_market"
                    ),
                    "execution_selection": prediction.get(
                        "execution_selection"
                    ),
                    "execution_score": prediction.get(
                        "execution_score"
                    ),
                    "execution_ready": prediction.get(
                        "execution_ready"
                    ),
                    "survivability_score": prediction.get(
                        "survivability_score"
                    ),
                    "bookmaker": prediction.get(
                        "bookmaker"
                    ),
                    "bookmaker_locality": prediction.get(
                        "bookmaker_locality"
                    ),
                    "local_realism_score": prediction.get(
                        "local_realism_score"
                    ),
                }
            )

        except Exception:
            continue

    alternatives.sort(
        key=lambda x: (
            x.get("confidence") or 0.0
        ),
        reverse=True,
    )

    return {
        "match": _match_payload(match),
        "count": len(alternatives),
        "markets": alternatives,
    }