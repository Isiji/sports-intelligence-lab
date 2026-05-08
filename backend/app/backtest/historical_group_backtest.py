from __future__ import annotations

from collections import defaultdict
from math import prod
from statistics import mean
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.backtest.settle import is_prediction_correct
from app.grouping.create_groups import group_predictions


def run_historical_group_backtest(
    session: Session,
    slate: str,
    stake: float = 100.0,
) -> dict[str, Any]:
    group_predictions(
        session=session,
        slate=slate,
        require_odds=True,
    )

    rows = session.execute(
        text(
            """
            SELECT
                pgi.group_name,

                p.id AS prediction_id,
                p.market,
                p.predicted_label,
                p.confidence,
                p.odds,
                p.value_score,

                m.id AS match_id,
                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                m.home_goals,
                m.away_goals,

                hs.corners AS home_corners,
                aws.corners AS away_corners,

                hs.shots_on_target AS home_sot,
                aws.shots_on_target AS away_sot

            FROM prediction_group_items pgi

            JOIN predictions p
                ON p.id = pgi.prediction_id

            JOIN matches m
                ON m.id = p.match_id

            LEFT JOIN team_match_stats hs
                ON hs.match_id = m.id
               AND hs.is_home = 1

            LEFT JOIN team_match_stats aws
                ON aws.match_id = m.id
               AND aws.is_home = 0

            WHERE pgi.slate = :slate

            ORDER BY
                pgi.group_name ASC,
                p.confidence DESC
            """
        ),
        {"slate": slate},
    ).mappings().all()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        grouped[row["group_name"]].append(dict(row))

    total_profit = 0.0
    total_groups = 0
    won_groups = 0
    lost_groups = 0

    reports = []

    bankroll = 10000.0

    for group_name, picks in grouped.items():
        total_groups += 1

        all_settled = True
        all_correct = True

        odds_values = []

        for pick in picks:
            odds = pick["odds"]

            if odds:
                odds_values.append(float(odds))

            if (
                pick["home_goals"] is None
                or pick["away_goals"] is None
            ):
                all_settled = False
                all_correct = False
                continue

            correct = is_prediction_correct(
                predicted_label=pick["predicted_label"],
                home_goals=int(pick["home_goals"]),
                away_goals=int(pick["away_goals"]),
                home_corners=pick["home_corners"],
                away_corners=pick["away_corners"],
                home_sot=pick["home_sot"],
                away_sot=pick["away_sot"],
            )

            if not correct:
                all_correct = False

        total_odds = (
            round(prod(odds_values), 4)
            if len(odds_values) == len(picks)
            else None
        )

        if not all_settled:
            outcome = "pending"
            profit = 0.0

        elif all_correct:
            outcome = "won"
            won_groups += 1

            profit = round(
                stake * ((total_odds or 1.0) - 1.0),
                2,
            )

            bankroll += profit

        else:
            outcome = "lost"
            lost_groups += 1

            profit = -stake
            bankroll -= stake

        total_profit += profit

        reports.append(
            {
                "group_name": group_name,
                "games": len(picks),
                "markets": sorted(
                    {pick["market"] for pick in picks}
                ),
                "leagues": sorted(
                    {pick["league"] for pick in picks}
                ),
                "average_confidence": round(
                    mean(
                        float(pick["confidence"] or 0.0)
                        for pick in picks
                    ),
                    4,
                ),
                "average_value_score": round(
                    mean(
                        float(pick["value_score"] or 0.0)
                        for pick in picks
                    ),
                    4,
                ),
                "total_odds": total_odds,
                "outcome": outcome,
                "profit": round(profit, 2),
                "bankroll": round(bankroll, 2),
            }
        )

    roi = (
        round(total_profit / (total_groups * stake), 4)
        if total_groups
        else 0.0
    )

    hit_rate = (
        round(won_groups / total_groups, 4)
        if total_groups
        else 0.0
    )

    return {
        "summary": {
            "groups": total_groups,
            "won_groups": won_groups,
            "lost_groups": lost_groups,
            "hit_rate": hit_rate,
            "total_profit": round(total_profit, 2),
            "roi": roi,
            "ending_bankroll": round(bankroll, 2),
        },
        "groups": reports,
    }