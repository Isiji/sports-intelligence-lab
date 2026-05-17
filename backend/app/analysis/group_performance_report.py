# backend/app/analysis/group_performance_report.py

from __future__ import annotations

from collections import defaultdict
from math import prod
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.backtest.settlement_engine import resolve_prediction_result
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

                p.odds_bookmaker,
                p.odds_market,
                p.odds_selection,
                p.odds_match_quality,

                p.production_score,
                p.risk_level,

                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                m.status,

                m.home_goals,
                m.away_goals

            FROM prediction_group_items pgi

            JOIN predictions p
                ON p.id = pgi.prediction_id

            JOIN matches m
                ON m.id = p.match_id

            WHERE pgi.slate = :slate

            ORDER BY
                pgi.group_name ASC,
                p.confidence DESC,
                p.id ASC
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
            if pick["odds"] is not None
            and float(pick["odds"]) > 0
        ]

        total_odds = (
            round(float(prod(odds_values)), 4)
            if len(odds_values) == len(picks)
            else None
        )

        settled_picks = []

        pending_count = 0
        won_count = 0
        lost_count = 0
        push_count = 0
        void_count = 0

        for pick in picks:
            if pick["home_goals"] is None or pick["away_goals"] is None:
                pending_count += 1

                settled_picks.append(
                    {
                        **pick,
                        "settled": False,
                        "settlement_status": "PENDING",
                        "correct": None,
                        "profit": 0.0,
                    }
                )

                continue

            result = resolve_prediction_result(
                predicted_label=pick["predicted_label"],
                home_goals=int(pick["home_goals"]),
                away_goals=int(pick["away_goals"]),
            )

            odds = float(pick["odds"] or 0.0)

            if result.status == "WON":
                won_count += 1
                profit = round(stake * (odds - 1.0), 2)

            elif result.status == "LOST":
                lost_count += 1
                profit = round(-stake, 2)

            elif result.status == "PUSH":
                push_count += 1
                profit = 0.0

            else:
                void_count += 1
                profit = 0.0

            settled_picks.append(
                {
                    **pick,
                    "settled": True,
                    "settlement_status": result.status,
                    "correct": result.status == "WON",
                    "profit": profit,
                    "settlement_reason": result.reason,
                }
            )

        settled_count = (
            won_count
            + lost_count
            + push_count
            + void_count
        )

        total_profit = round(
            sum(float(pick.get("profit") or 0.0) for pick in settled_picks),
            2,
        )

        total_stake = round(
            stake * max(settled_count, 1),
            2,
        )

        roi = (
            round(total_profit / total_stake, 4)
            if total_stake > 0
            else 0.0
        )

        if pending_count > 0:
            outcome = "pending"

        elif lost_count > 0:
            outcome = "lost"

        elif won_count > 0:
            outcome = "won"

        elif push_count > 0:
            outcome = "push"

        else:
            outcome = "void"

        group_type = _infer_group_type(
            group_name,
            picks,
        )

        reports.append(
            {
                "group_name": group_name,

                "group_type": group_type,

                "games": len(picks),

                "settled_games": settled_count,
                "pending_games": pending_count,

                "won_picks": won_count,
                "lost_picks": lost_count,
                "push_picks": push_count,
                "void_picks": void_count,

                "markets_used": sorted(
                    {
                        pick["market"]
                        for pick in picks
                    }
                ),

                "leagues_used": sorted(
                    {
                        pick["league"]
                        for pick in picks
                    }
                ),

                "bookmakers_used": sorted(
                    {
                        pick["odds_bookmaker"]
                        for pick in picks
                        if pick["odds_bookmaker"]
                    }
                ),

                "average_confidence": round(
                    sum(float(pick["confidence"] or 0.0) for pick in picks)
                    / len(picks),
                    4,
                ),

                "average_value_score": round(
                    sum(float(pick["value_score"] or 0.0) for pick in picks)
                    / len(picks),
                    4,
                ),

                "average_production_score": round(
                    sum(float(pick.get("production_score") or 0.0) for pick in picks)
                    / len(picks),
                    4,
                ),

                "total_odds": total_odds,

                "odds_coverage": round(
                    len(odds_values) / len(picks),
                    4,
                ),

                "outcome": outcome,

                "stake_per_pick": stake,

                "total_stake": total_stake,

                "profit": total_profit,

                "roi": roi,

                "average_risk_level": _average_risk_level(picks),

                "exact_executable_matches": sum(
                    1
                    for pick in picks
                    if pick.get("odds_match_quality") == "exact_executable_market"
                ),

                "reason": _group_reason(group_type),

                "picks": [
                    {
                        "prediction_id": pick["prediction_id"],

                        "match_id": pick["match_id"],

                        "league": pick["league"],

                        "home_team": pick["home_team"],
                        "away_team": pick["away_team"],

                        "kickoff_date": str(pick["kickoff_date"]),

                        "status": pick["status"],

                        "market": pick["market"],
                        "predicted_label": pick["predicted_label"],

                        "confidence": round(
                            float(pick["confidence"] or 0.0),
                            4,
                        ),

                        "odds": pick["odds"],

                        "value_score": pick["value_score"],

                        "bookmaker": pick["odds_bookmaker"],

                        "odds_market": pick["odds_market"],

                        "odds_selection": pick["odds_selection"],

                        "odds_match_quality": pick["odds_match_quality"],

                        "production_score": pick["production_score"],

                        "risk_level": pick["risk_level"],

                        "score": (
                            f"{pick['home_goals']}-{pick['away_goals']}"
                            if pick["home_goals"] is not None
                            and pick["away_goals"] is not None
                            else None
                        ),

                        "settled": pick["settled"],

                        "settlement_status": pick["settlement_status"],

                        "correct": pick["correct"],

                        "profit": pick.get("profit"),

                        "settlement_reason": pick.get("settlement_reason"),
                    }
                    for pick in settled_picks
                ],
            }
        )

    total_profit = round(
        sum(float(row["profit"]) for row in reports),
        2,
    )

    total_stake = round(
        sum(float(row["total_stake"]) for row in reports),
        2,
    )

    overall_roi = (
        round(total_profit / total_stake, 4)
        if total_stake > 0
        else 0.0
    )

    return {
        "slate": selected_slate,

        "groups_found": len(reports),

        "stake_per_group": stake,

        "summary": {
            "groups": len(reports),

            "won": sum(
                1
                for row in reports
                if row["outcome"] == "won"
            ),

            "lost": sum(
                1
                for row in reports
                if row["outcome"] == "lost"
            ),

            "pending": sum(
                1
                for row in reports
                if row["outcome"] == "pending"
            ),

            "push": sum(
                1
                for row in reports
                if row["outcome"] == "push"
            ),

            "void": sum(
                1
                for row in reports
                if row["outcome"] == "void"
            ),

            "total_profit": total_profit,

            "total_stake": total_stake,

            "overall_roi": overall_roi,
        },

        "groups": reports,
    }


def _average_risk_level(
    picks: list[dict[str, Any]],
) -> str:
    scores = {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "AVOID": 4,
    }

    reverse = {
        1: "LOW",
        2: "MEDIUM",
        3: "HIGH",
        4: "AVOID",
    }

    levels = [
        scores.get(
            str(pick.get("risk_level") or "MEDIUM").upper(),
            2,
        )
        for pick in picks
    ]

    if not levels:
        return "UNKNOWN"

    return reverse.get(
        round(sum(levels) / len(levels)),
        "MEDIUM",
    )


def _infer_group_type(
    group_name: str,
    picks: list[dict[str, Any]],
) -> str:
    if group_name.lower().startswith("portfolio group"):
        return "PROFITABILITY_PORTFOLIO"

    has_full_odds = all(
        pick["odds"] is not None
        for pick in picks
    )

    if has_full_odds:
        return "FALLBACK_VALUE_GROUP"

    return "FALLBACK_CONFIDENCE_GROUP"


def _group_reason(
    group_type: str,
) -> str:
    if group_type == "PROFITABILITY_PORTFOLIO":
        return "Created by strict profitability portfolio rules."

    if group_type == "FALLBACK_VALUE_GROUP":
        return (
            "Fallback group created because strict profitability "
            "portfolio did not find enough qualified candidates, "
            "but all picks had odds."
        )

    return (
        "Fallback confidence group created because strict "
        "profitability portfolio did not find enough qualified "
        "candidates and some picks lacked odds."
    )