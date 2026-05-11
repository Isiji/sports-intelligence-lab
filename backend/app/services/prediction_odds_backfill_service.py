# backend/app/services/prediction_odds_backfill_service.py

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MatchOdds, Prediction


@dataclass(frozen=True)
class OddsBackfillResult:
    prediction_id: int
    match_id: int
    market: str
    selection: str
    odds: float | None
    updated: bool
    reason: str | None = None


def backfill_prediction_odds(
    session: Session,
    slate: str,
    only_missing: bool = True,
    dry_run: bool = False,
) -> dict:
    query = (
        select(Prediction)
        .where(Prediction.slate == slate)
        .order_by(Prediction.id.asc())
    )

    if only_missing:
        query = query.where(Prediction.odds.is_(None))

    predictions = list(session.scalars(query))

    updated = 0
    skipped = 0
    results: list[OddsBackfillResult] = []

    for prediction in predictions:
        odds = find_prediction_odds(
            session=session,
            match_id=prediction.match_id,
            market=prediction.market,
            selection=prediction.predicted_label,
        )

        if odds is None:
            skipped += 1
            results.append(
                OddsBackfillResult(
                    prediction_id=prediction.id,
                    match_id=prediction.match_id,
                    market=prediction.market,
                    selection=prediction.predicted_label,
                    odds=None,
                    updated=False,
                    reason="no_matching_odds",
                )
            )
            continue

        implied_probability = round(1 / odds, 4)
        value_score = round(
            float(prediction.confidence or 0.0) - implied_probability,
            4,
        )

        if not dry_run:
            prediction.odds = odds
            prediction.implied_probability = implied_probability
            prediction.value_score = value_score

        updated += 1

        results.append(
            OddsBackfillResult(
                prediction_id=prediction.id,
                match_id=prediction.match_id,
                market=prediction.market,
                selection=prediction.predicted_label,
                odds=odds,
                updated=True,
            )
        )

    if not dry_run:
        session.commit()

    return {
        "slate": slate,
        "predictions_checked": len(predictions),
        "updated": updated,
        "skipped": skipped,
        "dry_run": dry_run,
        "sample_results": [
            result.__dict__
            for result in results[:30]
        ],
    }


def find_prediction_odds(
    session: Session,
    match_id: int,
    market: str,
    selection: str,
) -> float | None:
    normalized_market = normalize_market(market)
    normalized_selection = normalize_selection(selection)

    candidate_markets = build_market_candidates(
        normalized_market=normalized_market,
        normalized_selection=normalized_selection,
    )

    candidate_selections = build_selection_candidates(
        normalized_selection=normalized_selection,
    )

    rows = (
        session.query(MatchOdds)
        .filter(
            MatchOdds.match_id == match_id,
            MatchOdds.market.in_(candidate_markets),
            MatchOdds.selection.in_(candidate_selections),
        )
        .order_by(
            MatchOdds.odds.desc(),
            MatchOdds.retrieved_at.desc(),
            MatchOdds.id.desc(),
        )
        .all()
    )

    if not rows:
        return None

    best = rows[0]

    return round(float(best.odds), 4)

def build_market_candidates(
    normalized_market: str,
    normalized_selection: str,
) -> list[str]:
    candidates = {
        normalized_market,
    }

    # =====================================================
    # DOUBLE CHANCE
    # =====================================================

    if normalized_market.startswith("double_chance"):
        candidates.update(
            {
                "double_chance",
                "double_chance_1x",
                "double_chance_x2",
                "double_chance_12",
            }
        )

    # =====================================================
    # GOALS
    # =====================================================

    if "2_5" in normalized_market:
        candidates.update(
            {
                "over_under_2_5",
                "under_2_5_goals",
                "over_2_5_goals",
            }
        )

    if "1_5" in normalized_market:
        candidates.update(
            {
                "over_under_1_5",
                "under_1_5_goals",
                "over_1_5_goals",
            }
        )

    if "3_5" in normalized_market:
        candidates.update(
            {
                "over_under_3_5",
                "under_3_5_goals",
                "over_3_5_goals",
            }
        )

    # =====================================================
    # BTTS
    # =====================================================

    if "btts" in normalized_market:
        candidates.update(
            {
                "btts",
                "both_teams_to_score",
            }
        )

    return list(candidates)


def build_selection_candidates(
    normalized_selection: str,
) -> list[str]:
    candidates = {
        normalized_selection,
    }

    mapping = {
        "DOUBLE_CHANCE_1X": ["1X"],
        "DOUBLE_CHANCE_X2": ["X2"],
        "DOUBLE_CHANCE_12": ["12"],

        "OVER_1_5": ["OVER", "O1.5"],
        "UNDER_1_5": ["UNDER", "U1.5"],

        "OVER_2_5": ["OVER", "O2.5"],
        "UNDER_2_5": ["UNDER", "U2.5"],

        "OVER_3_5": ["OVER", "O3.5"],
        "UNDER_3_5": ["UNDER", "U3.5"],

        "BTTS_YES": ["YES"],
        "BTTS_NO": ["NO"],

        "HOME_WIN": ["HOME", "1"],
        "DRAW": ["DRAW", "X"],
        "AWAY_WIN": ["AWAY", "2"],
    }

    for alt in mapping.get(normalized_selection, []):
        candidates.add(alt)

    return list(candidates)

def normalize_market(value: str) -> str:
    return str(value or "").strip().lower()


def normalize_selection(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )