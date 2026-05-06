# backend/app/grouping/create_groups.py

from math import prod
from statistics import mean

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Prediction, PredictionGroupItem


def group_predictions(
    session: Session,
    slate: str,
    min_confidence: float = 0.65,
    min_group_odds: float = 3.0,
) -> dict[str, dict[str, float]]:
    predictions = list(
        session.scalars(
            select(Prediction)
            .where(
                Prediction.slate == slate,
                Prediction.confidence >= min_confidence,
            )
            .order_by(Prediction.confidence.desc(), Prediction.id.asc())
        )
    )

    best_prediction_by_match: dict[int, Prediction] = {}

    for prediction in predictions:
        current_best = best_prediction_by_match.get(prediction.match_id)

        if current_best is None:
            best_prediction_by_match[prediction.match_id] = prediction
            continue

        current_score = _ranking_score(current_best)
        new_score = _ranking_score(prediction)

        if new_score > current_score:
            best_prediction_by_match[prediction.match_id] = prediction

    ranked_games = sorted(
        best_prediction_by_match.values(),
        key=lambda prediction: (-_ranking_score(prediction), prediction.id),
    )

    group_sizes = _group_sizes(
    total_games=len(ranked_games),
    max_groups=10,
    min_group_size=4,
    max_group_size=5,
    )

    session.execute(
        delete(PredictionGroupItem).where(PredictionGroupItem.slate == slate)
    )

    index = 0
    group_summaries: dict[str, dict[str, float]] = {}

    for group_number, size in enumerate(group_sizes, start=1):
        group_name = f"Group {group_number}"

        selected_games = ranked_games[index : index + size]
        index += size

        if not selected_games:
            continue

        cumulative_odds = _cumulative_odds(selected_games)

        if cumulative_odds is not None and cumulative_odds < min_group_odds:
            selected_games = _boost_group_to_min_odds(
                selected_games=selected_games,
                available_games=ranked_games,
                min_group_odds=min_group_odds,
            )
            cumulative_odds = _cumulative_odds(selected_games)

        for prediction in selected_games:
            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=prediction.id,
                )
            )

        group_summaries[group_name] = {
            "average_confidence": round(mean([p.confidence for p in selected_games]), 4),
            "cumulative_odds": round(cumulative_odds, 4) if cumulative_odds else 0.0,
            "games": float(len(selected_games)),
        }

    session.commit()

    return group_summaries


def _ranking_score(prediction: Prediction) -> float:
    value_score = prediction.value_score or 0.0
    odds_bonus = 0.0

    if prediction.odds:
        odds_bonus = min(prediction.odds / 10, 0.2)

    return prediction.confidence + value_score + odds_bonus


def _cumulative_odds(predictions: list[Prediction]) -> float | None:
    odds_values = [p.odds for p in predictions if p.odds is not None]

    if len(odds_values) != len(predictions):
        return None

    return float(prod(odds_values))


def _boost_group_to_min_odds(
    selected_games: list[Prediction],
    available_games: list[Prediction],
    min_group_odds: float,
) -> list[Prediction]:
    selected_ids = {p.id for p in selected_games}
    candidates = [p for p in available_games if p.id not in selected_ids and p.odds]

    current = selected_games[:]

    for i in range(len(current)):
        best_replacement = None
        best_odds = _cumulative_odds(current) or 0.0

        for candidate in candidates:
            test_group = current[:]
            test_group[i] = candidate

            test_odds = _cumulative_odds(test_group) or 0.0

            if test_odds > best_odds:
                best_odds = test_odds
                best_replacement = candidate

        if best_replacement:
            current[i] = best_replacement

        final_odds = _cumulative_odds(current)

        if final_odds and final_odds >= min_group_odds:
            break

    return current


def _group_sizes(
    total_games: int,
    max_groups: int = 10,
    min_group_size: int = 4,
    max_group_size: int = 5,
) -> list[int]:
    if total_games < min_group_size:
        raise ValueError(
            f"Need at least {min_group_size} games to create groups."
        )

    usable_games = min(total_games, max_groups * max_group_size)

    group_count = min(max_groups, usable_games // min_group_size)

    if group_count < 1:
        raise ValueError("Not enough games to create groups.")

    sizes = [min_group_size for _ in range(group_count)]

    remaining = usable_games - (group_count * min_group_size)

    index = 0
    while remaining > 0 and index < group_count:
        if sizes[index] < max_group_size:
            sizes[index] += 1
            remaining -= 1
        index += 1

    return sizes