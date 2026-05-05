# backend/app/grouping/create_groups.py

from statistics import mean

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Prediction, PredictionGroupItem


def group_predictions(session: Session, slate: str) -> dict[str, float]:
    predictions = list(
        session.scalars(
            select(Prediction)
            .where(Prediction.slate == slate)
            .order_by(Prediction.confidence.desc(), Prediction.id.asc())
        )
    )

    group_sizes = _group_sizes(len(predictions))

    session.execute(
        delete(PredictionGroupItem).where(PredictionGroupItem.slate == slate)
    )

    index = 0
    group_averages: dict[str, float] = {}

    for group_number, size in enumerate(group_sizes, start=1):
        group_name = f"Group {group_number}"
        group_items = predictions[index : index + size]
        index += size

        for prediction in group_items:
            session.add(
                PredictionGroupItem(
                    slate=slate,
                    group_name=group_name,
                    prediction_id=prediction.id,
                )
            )

        group_averages[group_name] = round(
            mean(prediction.confidence for prediction in group_items),
            4,
        )

    session.commit()

    return group_averages


def _group_sizes(total_predictions: int) -> list[int]:
    if total_predictions < 12:
        raise ValueError("Need at least 12 predictions to create 4 groups of 3-4 games.")

    usable_predictions = min(total_predictions, 16)

    sizes = [3, 3, 3, 3]
    extra_predictions = usable_predictions - 12

    for index in range(extra_predictions):
        sizes[index] += 1

    return sizes