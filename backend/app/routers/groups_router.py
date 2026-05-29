# backend/app/routers/groups_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.grouping.create_groups import group_predictions
from app.schemas.groups import (
    GroupCreateResponse,
    GroupItemResponse,
)
from app.utils.slate import resolve_slate


router = APIRouter(
    prefix="/groups",
    tags=["Groups"],
)


@router.post(
    "/create",
    response_model=GroupCreateResponse,
)
def create_prediction_groups(
    slate: str | None = Query(None),
    min_confidence: float = Query(0.65, ge=0.5, le=0.99),
    min_group_odds: float = Query(3.0, ge=1.0),
    require_odds: bool = Query(False),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    try:
        summaries = group_predictions(
            session=session,
            slate=selected_slate,
            min_confidence=min_confidence,
            min_group_odds=min_group_odds,
            require_odds=require_odds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GroupCreateResponse(
        slate=selected_slate,
        group_summaries=summaries,
    )


@router.get(
    "",
    response_model=list[GroupItemResponse],
)
def list_prediction_groups(
    slate: str | None = Query(None),
    limit: int = Query(300, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    query = text(
        """
        SELECT
            pgi.group_name,
            pgi.prediction_id,
            p.match_id,

            m.league,
            TO_CHAR(
                m.kickoff_datetime AT TIME ZONE 'Africa/Nairobi',
                'YYYY-MM-DD HH24:MI'
            ) AS kickoff_eat,

            m.home_team,
            m.away_team,

            p.market,
            p.predicted_label,
            p.confidence,

            p.odds,
            p.value_score,

            p.execution_market,
            p.execution_selection,
            p.execution_score,
            p.survivability_score,
            p.local_realism_score,
            p.execution_ready,

            p.odds_bookmaker,
            p.bookmaker_locality,
            p.execution_reasons

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

        LIMIT :limit
        """
    )

    rows = session.execute(
        query,
        {
            "slate": selected_slate,
            "limit": limit,
        },
    ).mappings().all()

    return [
        GroupItemResponse(**row)
        for row in rows
    ]