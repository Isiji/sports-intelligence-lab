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

        home_win = match.home_goals > match.away_goals

        prediction_correct = (
            prediction.predicted_label == "HOME_WIN"
            and home_win
        ) or (
            prediction.predicted_label == "NOT_HOME_WIN"
            and not home_win
        )

        if prediction_correct:
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