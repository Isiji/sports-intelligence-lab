# backend/app/services/production_review_service.py

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.services.production_pick_scoring_service import score_pick_list
from app.intelligence.exposure_control import (
    apply_exposure_controls,
)

from app.intelligence.pick_recommendation_engine import (
    build_recommendation_layer,
)

def get_production_review(
    session: Session,
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    selected_slate = slate or f"football_{date.today().isoformat()}"

    filters = ["p.slate = :slate"]

    params: dict[str, Any] = {
        "slate": selected_slate,
        "limit": limit,
    }

    if market:
        filters.append("p.market = :market")
        params["market"] = market

    if league:
        filters.append("m.league = :league")
        params["league"] = league

    if require_odds:
        filters.append("p.odds IS NOT NULL")

    where_clause = " AND ".join(filters)

    prediction_summary = session.execute(
        text(
            f"""
            SELECT
                COUNT(*) AS total_predictions,
                COUNT(CASE WHEN p.odds IS NOT NULL THEN 1 END) AS predictions_with_odds,
                COUNT(CASE WHEN p.value_score IS NOT NULL THEN 1 END) AS predictions_with_value,
                AVG(p.confidence) AS avg_confidence,
                AVG(p.odds) AS avg_odds,
                AVG(p.value_score) AS avg_value_score
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE {where_clause}
            """
        ),
        params,
    ).mappings().first()

    ranked_picks = session.execute(
        text(
            f"""
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
            WHERE {where_clause}
            ORDER BY
                COALESCE(p.value_score, 0) DESC,
                p.confidence DESC,
                COALESCE(p.odds, 0) DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    best_picks_per_match = session.execute(
        text(
            f"""
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
                WHERE {where_clause}
            ) ranked
            WHERE pick_rank = 1
            ORDER BY
                COALESCE(value_score, 0) DESC,
                confidence DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    market_summary = session.execute(
        text(
            f"""
            SELECT
                p.market,
                COUNT(*) AS picks,
                COUNT(CASE WHEN p.odds IS NOT NULL THEN 1 END) AS picks_with_odds,
                AVG(p.confidence) AS avg_confidence,
                AVG(p.odds) AS avg_odds,
                AVG(p.value_score) AS avg_value_score
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE {where_clause}
            GROUP BY p.market
            ORDER BY
                AVG(p.value_score) DESC NULLS LAST,
                AVG(p.confidence) DESC
            """
        ),
        params,
    ).mappings().all()

    league_summary = session.execute(
        text(
            f"""
            SELECT
                m.league,
                COUNT(*) AS picks,
                COUNT(CASE WHEN p.odds IS NOT NULL THEN 1 END) AS picks_with_odds,
                AVG(p.confidence) AS avg_confidence,
                AVG(p.odds) AS avg_odds,
                AVG(p.value_score) AS avg_value_score
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE {where_clause}
            GROUP BY m.league
            ORDER BY
                AVG(p.value_score) DESC NULLS LAST,
                AVG(p.confidence) DESC
            LIMIT 50
            """
        ),
        params,
    ).mappings().all()

    group_items = session.execute(
        text(
            f"""
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
            WHERE {where_clause}
            ORDER BY
                pgi.group_name,
                COALESCE(p.value_score, 0) DESC,
                p.confidence DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    scored_ranked_picks = score_pick_list(
        [dict(row) for row in ranked_picks]
    )

    scored_best_picks = score_pick_list(
        [dict(row) for row in best_picks_per_match]
    )

    scored_group_items = score_pick_list(
        [dict(row) for row in group_items]
    )

    exposure_result = apply_exposure_controls(
        picks=scored_best_picks,
    )

    recommendation_layer = build_recommendation_layer(
        exposure_result=exposure_result,
    )

    return {
        "slate": selected_slate,
        "filters": {
            "market": market,
            "league": league,
            "require_odds": require_odds,
            "limit": limit,
        },
        "prediction_summary": dict(prediction_summary or {}),
        "ranked_picks": scored_ranked_picks,
        "exposure_control": exposure_result,
        "best_picks_per_match": scored_best_picks,
        "recommendations": recommendation_layer,
        "market_summary": [
            dict(row)
            for row in market_summary
        ],
        "league_summary": [
            dict(row)
            for row in league_summary
        ],
        "group_items": scored_group_items,
    }