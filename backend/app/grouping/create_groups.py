# backend/app/grouping/create_groups.py

from statistics import mean

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Prediction, PredictionGroupItem


def group_predictions(session: Session, slate: str) -> dict[str, float]:
    """
    Create 4 groups of 3-4 games.

    Important:
    - A match can have several predictions/markets.
    - But for grouping, one match counts as one game.
    - We rank each match using its highest-confidence prediction.
    - Then we add ALL predictions for that selected match into the group.
    """

    predictions = list(
        session.scalars(
            select(Prediction)
            .where(Prediction.slate == slate)
            .order_by(Prediction.confidence.desc(), Prediction.id.asc())
        )
    )

    best_prediction_by_match: dict[int, Prediction] = {}

    for prediction in predictions:
        current_best = best_prediction_by_match.get(prediction.match_id)

        if current_best is None or prediction.confidence > current_best.confidence:
            best_prediction_by_match[prediction.match_id] = prediction

    ranked_games = sorted(
        best_prediction_by_match.values(),
        key=lambda prediction: (-prediction.confidence, prediction.id),
    )

    group_sizes = _group_sizes(len(ranked_games))

    session.execute(
        delete(PredictionGroupItem).where(PredictionGroupItem.slate == slate)
    )

    predictions_by_match: dict[int, list[Prediction]] = {}

    for prediction in predictions:
        predictions_by_match.setdefault(prediction.match_id, []).append(prediction)

    index = 0
    group_averages: dict[str, float] = {}

    for group_number, size in enumerate(group_sizes, start=1):
        group_name = f"Group {group_number}"
        selected_games = ranked_games[index : index + size]
        index += size

        group_confidences = []

        for selected_game in selected_games:
            match_predictions = predictions_by_match[selected_game.match_id]

            group_confidences.append(selected_game.confidence)

            for prediction in match_predictions:
                session.add(
                    PredictionGroupItem(
                        slate=slate,
                        group_name=group_name,
                        prediction_id=prediction.id,
                    )
                )

        group_averages[group_name] = round(mean(group_confidences), 4)

    session.commit()

    return group_averages


def _group_sizes(total_games: int) -> list[int]:
    if total_games < 12:
        raise ValueError("Need at least 12 games to create 4 groups of 3-4 games.")

    usable_games = min(total_games, 16)

    sizes = [3, 3, 3, 3]
    extra_games = usable_games - 12

    for index in range(extra_games):
        sizes[index] += 1

    return sizes