from __future__ import annotations

from collections import defaultdict
from math import prod
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.settle import is_prediction_correct
from app.db.models import Match, Prediction
from app.grouping.create_groups import group_predictions
from app.ml.train_football import (
    _train_market_model,
    load_training_frame,
    filter_training_frame_for_market,
    MARKET_TARGETS,
)
def rolling_group_backtest(
    session: Session,
    market: str,
    initial_train_size: int = 100,
    test_window_size: int = 20,
    limit: int = 100,
    min_confidence: float = 0.65,
    stake: float = 100.0,
):
    finished_matches = list(
        session.scalars(
            select(Match)
            .where(
                Match.has_odds.is_(True),
                Match.home_goals.isnot(None),
                Match.away_goals.isnot(None),
            )
            .order_by(Match.kickoff_date.asc())
        )
    )

    if len(finished_matches) < initial_train_size + test_window_size:
        raise ValueError("Not enough finished matches.")

    bankroll = 10000.0

    total_groups = 0
    won_groups = 0
    lost_groups = 0

    reports = []

    start_index = initial_train_size

    while start_index < len(finished_matches):
        end_index = start_index + test_window_size

        historical_test_matches = finished_matches[start_index:end_index]

        if not historical_test_matches:
            break

        print(
            f"[ROLLING GROUP BACKTEST] "
            f"train_end={start_index} "
            f"test_end={end_index}"
        )

        df = load_training_frame(session)

        market_df = filter_training_frame_for_market(
            df,
            market,
        )

        _train_market_model(
            session=session,
            df=market_df,
            market=market,
            target_column=MARKET_TARGETS[market],
        )

        slate = f"rolling_{market}_{start_index}_{end_index}"

        created_predictions = []

        for match in historical_test_matches:
            prediction = session.scalar(
                select(Prediction)
                .where(
                    Prediction.match_id == match.id,
                    Prediction.market == market,
                )
                .order_by(Prediction.id.desc())
            )

            if prediction is None:
                continue

            if prediction.confidence < min_confidence:
                continue

            prediction.slate = slate
            created_predictions.append(prediction)

        session.commit()

        if len(created_predictions) < 4:
            start_index += test_window_size
            continue

        group_predictions(
            session=session,
            slate=slate,
            require_odds=True,
        )

        grouped: dict[str, list[Prediction]] = defaultdict(list)

        slate_predictions = list(
            session.scalars(
                select(Prediction)
                .where(Prediction.slate == slate)
            )
        )

        for prediction in slate_predictions:
            grouped[prediction.slate].append(prediction)

        for group_name, predictions in grouped.items():
            total_groups += 1

            all_correct = True
            odds_values = []

            leagues = set()
            markets = set()

            for prediction in predictions:
                match = session.get(Match, prediction.match_id)

                if match is None:
                    all_correct = False
                    break

                leagues.add(match.league)
                markets.add(prediction.market)

                if prediction.odds:
                    odds_values.append(float(prediction.odds))

                correct = is_prediction_correct(
                    predicted_label=prediction.predicted_label,
                    home_goals=int(match.home_goals),
                    away_goals=int(match.away_goals),
                )

                if not correct:
                    all_correct = False

            total_odds = (
                round(prod(odds_values), 4)
                if odds_values
                else None
            )

            if all_correct:
                won_groups += 1

                profit = round(
                    stake * ((total_odds or 1.0) - 1.0),
                    2,
                )

                bankroll += profit
                outcome = "won"

            else:
                lost_groups += 1

                profit = -stake
                bankroll -= stake
                outcome = "lost"

            reports.append(
                {
                    "group_name": group_name,
                    "outcome": outcome,
                    "profit": round(profit, 2),
                    "bankroll": round(bankroll, 2),
                    "games": len(predictions),
                    "markets": sorted(markets),
                    "leagues": sorted(leagues),
                    "average_confidence": round(
                        mean(
                            p.confidence
                            for p in predictions
                        ),
                        4,
                    ),
                    "total_odds": total_odds,
                }
            )

            if total_groups >= limit:
                break

        if total_groups >= limit:
            break

        start_index += test_window_size

    roi = (
        round(total_groups and (bankroll - 10000.0) / (total_groups * stake), 4)
    )

    hit_rate = (
        round(won_groups / total_groups, 4)
        if total_groups
        else 0.0
    )

    return {
        "market": market,
        "groups": total_groups,
        "won_groups": won_groups,
        "lost_groups": lost_groups,
        "hit_rate": hit_rate,
        "ending_bankroll": round(bankroll, 2),
        "profit": round(bankroll - 10000.0, 2),
        "roi": roi,
        "reports": reports,
    }