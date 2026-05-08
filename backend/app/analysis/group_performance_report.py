from __future__ import annotations

from collections import defaultdict
from math import prod
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.backtest.settle import is_prediction_correct
from app.utils.slate import resolve_slate


def build_group_performance_report(
    session: Session,
    slate: str | None = None,
    stake: float = 100.0,
) -> dict[str, Any]:
    selected_slate = resolve_slate(slate)

    rows = session.execute(
        text(
            """
            SELECT
                pgi.group_name,
                p.id AS prediction_id,
                p.match_id,
                p.market,
                p.predicted_label,
                p.confidence,
                p.odds,
                p.value_score,
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
            ORDER BY pgi.group_name ASC, p.confidence DESC, p.id ASC
            """
        ),
        {"slate": selected_slate},
    ).mappings().all()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        grouped[row["group_name"]].append(dict(row))

    reports: list[dict[str, Any]] = []

    for group_name, picks in grouped.items():
        odds_values = [
            float(pick["odds"])
            for pick in picks
            if pick["odds"] is not None and float(pick["odds"]) > 0
        ]

        total_odds = (
            round(float(prod(odds_values)), 4)
            if len(odds_values) == len(picks)
            else None
        )

        settled_picks = []
        pending_count = 0

        for pick in picks:
            if pick["home_goals"] is None or pick["away_goals"] is None:
                pending_count += 1
                settled_picks.append(
                    {
                        **pick,
                        "settled": False,
                        "correct": None,
                    }
                )
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

            settled_picks.append(
                {
                    **pick,
                    "settled": True,
                    "correct": correct,
                }
            )

        settled_count = len(picks) - pending_count
        lost_count = sum(1 for pick in settled_picks if pick["correct"] is False)
        won_count = sum(1 for pick in settled_picks if pick["correct"] is True)

        if pending_count > 0:
            outcome = "pending"
            profit = 0.0
            roi = 0.0
        elif lost_count > 0:
            outcome = "lost"
            profit = -stake
            roi = -1.0
        else:
            outcome = "won"
            profit = round(stake * ((total_odds or 0.0) - 1.0), 2)
            roi = round(profit / stake, 4) if stake else 0.0

        group_type = _infer_group_type(group_name, picks)

        reports.append(
            {
                "group_name": group_name,
                "group_type": group_type,
                "games": len(picks),
                "settled_games": settled_count,
                "pending_games": pending_count,
                "won_picks": won_count,
                "lost_picks": lost_count,
                "markets_used": sorted({pick["market"] for pick in picks}),
                "leagues_used": sorted({pick["league"] for pick in picks}),
                "average_confidence": round(
                    sum(float(pick["confidence"] or 0.0) for pick in picks) / len(picks),
                    4,
                ),
                "average_value_score": round(
                    sum(float(pick["value_score"] or 0.0) for pick in picks) / len(picks),
                    4,
                ),
                "total_odds": total_odds,
                "odds_coverage": round(len(odds_values) / len(picks), 4),
                "outcome": outcome,
                "stake": stake,
                "profit": profit,
                "roi": roi,
                "reason": _group_reason(group_type),
                "picks": [
                    {
                        "prediction_id": pick["prediction_id"],
                        "match_id": pick["match_id"],
                        "league": pick["league"],
                        "home_team": pick["home_team"],
                        "away_team": pick["away_team"],
                        "kickoff_date": str(pick["kickoff_date"]),
                        "market": pick["market"],
                        "predicted_label": pick["predicted_label"],
                        "confidence": round(float(pick["confidence"] or 0.0), 4),
                        "odds": pick["odds"],
                        "value_score": pick["value_score"],
                        "score": (
                            f"{pick['home_goals']}-{pick['away_goals']}"
                            if pick["home_goals"] is not None and pick["away_goals"] is not None
                            else None
                        ),
                        "settled": pick["settled"],
                        "correct": pick["correct"],
                    }
                    for pick in settled_picks
                ],
            }
        )

    return {
        "slate": selected_slate,
        "groups_found": len(reports),
        "stake_per_group": stake,
        "summary": {
            "groups": len(reports),
            "won": sum(1 for row in reports if row["outcome"] == "won"),
            "lost": sum(1 for row in reports if row["outcome"] == "lost"),
            "pending": sum(1 for row in reports if row["outcome"] == "pending"),
            "total_profit": round(sum(float(row["profit"]) for row in reports), 2),
        },
        "groups": reports,
    }


def _infer_group_type(group_name: str, picks: list[dict[str, Any]]) -> str:
    if group_name.lower().startswith("portfolio group"):
        return "PROFITABILITY_PORTFOLIO"

    has_full_odds = all(pick["odds"] is not None for pick in picks)

    if has_full_odds:
        return "FALLBACK_VALUE_GROUP"

    return "FALLBACK_CONFIDENCE_GROUP"


def _group_reason(group_type: str) -> str:
    if group_type == "PROFITABILITY_PORTFOLIO":
        return "Created by strict profitability portfolio rules."

    if group_type == "FALLBACK_VALUE_GROUP":
        return "Fallback group created because strict profitability portfolio did not find enough qualified candidates, but all picks had odds."

    return "Fallback confidence group created because strict profitability portfolio did not find enough qualified candidates and some picks lacked odds."