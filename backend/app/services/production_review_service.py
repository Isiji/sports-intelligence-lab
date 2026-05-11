# backend/app/services/production_review_service.py

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_production_review(
    session: Session,
    slate: str | None = None,
) -> dict[str, Any]:
    selected_slate = slate or f"football_{date.today().isoformat()}"

    prediction_summary = session.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_predictions,
                COUNT(CASE WHEN odds IS NOT NULL THEN 1 END) AS predictions_with_odds,
                COUNT(CASE WHEN value_score IS NOT NULL THEN 1 END) AS predictions_with_value,
                AVG(confidence) AS avg_confidence,
                AVG(odds) AS avg_odds,
                AVG(value_score) AS avg_value_score
            FROM predictions
            WHERE slate = :slate
            """
        ),
        {"slate": selected_slate},
    ).mappings().first()

    ranked_picks = session.execute(
        text(
            """
            SELECT
                p.id AS prediction_id,
                p.match_id,
                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                p.market,
                p.predicted_label,
                p.confidence,
                p.odds,
                p.implied_probability,
                p.value_score,
                p.model_name
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.slate = :slate
            ORDER BY
                COALESCE(p.value_score, 0) DESC,
                p.confidence DESC,
                COALESCE(p.odds, 0) DESC
            LIMIT 100
            """
        ),
        {"slate": selected_slate},
    ).mappings().all()

    best_picks_per_match = session.execute(
        text(
            """
            SELECT *
            FROM (
                SELECT
                    p.id AS prediction_id,
                    p.match_id,
                    m.league,
                    m.home_team,
                    m.away_team,
                    m.kickoff_date,
                    p.market,
                    p.predicted_label,
                    p.confidence,
                    p.odds,
                    p.implied_probability,
                    p.value_score,
                    p.model_name,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.match_id
                        ORDER BY
                            COALESCE(p.value_score, 0) DESC,
                            p.confidence DESC,
                            COALESCE(p.odds, 0) DESC
                    ) AS pick_rank
                FROM predictions p
                JOIN matches m ON m.id = p.match_id
                WHERE p.slate = :slate
            ) ranked
            WHERE pick_rank = 1
            ORDER BY
                COALESCE(value_score, 0) DESC,
                confidence DESC
            LIMIT 100
            """
        ),
        {"slate": selected_slate},
    ).mappings().all()

    market_summary = session.execute(
        text(
            """
            SELECT
                market,
                COUNT(*) AS picks,
                COUNT(CASE WHEN odds IS NOT NULL THEN 1 END) AS picks_with_odds,
                AVG(confidence) AS avg_confidence,
                AVG(odds) AS avg_odds,
                AVG(value_score) AS avg_value_score
            FROM predictions
            WHERE slate = :slate
            GROUP BY market
            ORDER BY
                AVG(value_score) DESC NULLS LAST,
                AVG(confidence) DESC
            """
        ),
        {"slate": selected_slate},
    ).mappings().all()

    league_summary = session.execute(
        text(
            """
            SELECT
                m.league,
                COUNT(*) AS picks,
                COUNT(CASE WHEN p.odds IS NOT NULL THEN 1 END) AS picks_with_odds,
                AVG(p.confidence) AS avg_confidence,
                AVG(p.odds) AS avg_odds,
                AVG(p.value_score) AS avg_value_score
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.slate = :slate
            GROUP BY m.league
            ORDER BY
                AVG(p.value_score) DESC NULLS LAST,
                AVG(p.confidence) DESC
            LIMIT 50
            """
        ),
        {"slate": selected_slate},
    ).mappings().all()

    group_items = session.execute(
        text(
            """
            SELECT
                pgi.group_name,
                p.id AS prediction_id,
                p.match_id,
                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,
                p.market,
                p.predicted_label,
                p.confidence,
                p.odds,
                p.value_score
            FROM prediction_group_items pgi
            JOIN predictions p ON p.id = pgi.prediction_id
            JOIN matches m ON m.id = p.match_id
            WHERE p.slate = :slate
            ORDER BY
                pgi.group_name,
                COALESCE(p.value_score, 0) DESC,
                p.confidence DESC
            """
        ),
        {"slate": selected_slate},
    ).mappings().all()

    return {
        "slate": selected_slate,
        "prediction_summary": dict(prediction_summary or {}),
        "ranked_picks": [dict(row) for row in ranked_picks],
        "best_picks_per_match": [dict(row) for row in best_picks_per_match],
        "market_summary": [dict(row) for row in market_summary],
        "league_summary": [dict(row) for row in league_summary],
        "group_items": [dict(row) for row in group_items],
    }