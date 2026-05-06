# backend/app/routers/dashboard_router.py

from math import prod

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.dashboard import DashboardResponse, GamePrediction, GroupSummary


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardResponse)
def get_dashboard_summary(
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    query = text(
        """
        SELECT
            pgi.group_name,
            m.home_team,
            m.away_team,
            p.market,
            p.predicted_label,
            p.confidence,
            p.odds,
            p.value_score
        FROM prediction_group_items pgi
        JOIN predictions p ON p.id = pgi.prediction_id
        JOIN matches m ON m.id = p.match_id
        WHERE pgi.slate = :slate
        ORDER BY pgi.group_name ASC, p.confidence DESC
        """
    )

    rows = session.execute(query, {"slate": slate}).mappings().all()

    groups_map: dict[str, list[GamePrediction]] = {}

    for row in rows:
        group_name = row["group_name"]

        game = GamePrediction(
            home_team=row["home_team"],
            away_team=row["away_team"],
            market=row["market"],
            predicted_label=row["predicted_label"],
            confidence=row["confidence"],
            odds=row["odds"],
            value_score=row["value_score"],
        )

        groups_map.setdefault(group_name, []).append(game)

    group_summaries = []

    for group_name, games in groups_map.items():
        avg_conf = round(sum(g.confidence for g in games) / len(games), 4)

        odds_values = [g.odds for g in games if g.odds is not None]
        cumulative_odds = round(prod(odds_values), 4) if len(odds_values) == len(games) else 0.0

        group_summaries.append(
            GroupSummary(
                group_name=group_name,
                average_confidence=avg_conf,
                cumulative_odds=cumulative_odds,
                games=games,
            )
        )

    return DashboardResponse(
        slate=slate,
        groups=group_summaries,
    )