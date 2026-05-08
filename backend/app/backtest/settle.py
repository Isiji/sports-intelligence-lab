# backend/app/backtest/settle.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BacktestRun, Match, Prediction


def settle_and_score(session: Session, slate: str) -> BacktestRun:
    predictions = list(
        session.scalars(
            select(Prediction).where(Prediction.slate == slate)
        )
    )

    if not predictions:
        raise ValueError(f"No predictions found for slate '{slate}'.")

    correct = 0
    settled = 0
    model_name = predictions[0].model_name

    for prediction in predictions:
        match = session.get(Match, prediction.match_id)

        if match is None:
            continue

        if match.home_goals is None or match.away_goals is None:
            continue

        settled += 1

        if is_prediction_correct(
            predicted_label=prediction.predicted_label,
            home_goals=match.home_goals,
            away_goals=match.away_goals,
        ):
            correct += 1

    overall_accuracy = correct / settled if settled else 0.0

    backtest_run = BacktestRun(
        slate=slate,
        model_name=model_name,
        overall_accuracy=round(overall_accuracy, 4),
        settled_predictions=settled,
    )

    session.add(backtest_run)
    session.commit()
    session.refresh(backtest_run)

    return backtest_run


def normalize_label(label: str) -> str:
    return label.strip().upper().replace("-", "_").replace(" ", "_").replace(".", "_")


def is_prediction_correct(
    predicted_label: str,
    home_goals: int,
    away_goals: int,
    home_corners: int | None = None,
    away_corners: int | None = None,
    home_sot: int | None = None,
    away_sot: int | None = None,
) -> bool:
    label = normalize_label(predicted_label)
    total_goals = home_goals + away_goals

    if label == "HOME_WIN":
        return home_goals > away_goals

    if label == "NOT_HOME_WIN":
        return home_goals <= away_goals

    if label == "AWAY_WIN":
        return away_goals > home_goals

    if label == "NOT_AWAY_WIN":
        return away_goals <= home_goals

    if label == "DRAW":
        return home_goals == away_goals

    if label == "NOT_DRAW":
        return home_goals != away_goals

    if label == "DOUBLE_CHANCE_1X":
        return home_goals >= away_goals

    if label == "NOT_DOUBLE_CHANCE_1X":
        return home_goals < away_goals

    if label == "DOUBLE_CHANCE_X2":
        return away_goals >= home_goals

    if label == "NOT_DOUBLE_CHANCE_X2":
        return home_goals > away_goals

    if label == "DOUBLE_CHANCE_12":
        return home_goals != away_goals

    if label == "NOT_DOUBLE_CHANCE_12":
        return home_goals == away_goals

    if label == "OVER_1_5":
        return total_goals > 1.5

    if label == "UNDER_1_5":
        return total_goals < 1.5

    if label == "OVER_2_5":
        return total_goals > 2.5

    if label == "UNDER_2_5":
        return total_goals < 2.5

    if label == "OVER_3_5":
        return total_goals > 3.5

    if label == "UNDER_3_5":
        return total_goals < 3.5

    if label == "BTTS_YES":
        return home_goals > 0 and away_goals > 0

    if label == "BTTS_NO":
        return home_goals == 0 or away_goals == 0

    if label == "CORNERS_OVER_8_5":
        if home_corners is None or away_corners is None:
            return False
        return home_corners + away_corners > 8.5

    if label == "CORNERS_UNDER_8_5":
        if home_corners is None or away_corners is None:
            return False
        return home_corners + away_corners < 8.5

    if label == "SOT_OVER_8_5":
        if home_sot is None or away_sot is None:
            return False
        return home_sot + away_sot > 8.5

    if label == "SOT_UNDER_8_5":
        if home_sot is None or away_sot is None:
            return False
        return home_sot + away_sot < 8.5

    return False