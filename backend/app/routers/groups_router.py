# backend/app/routers/groups_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.grouping.create_groups import group_predictions
from app.schemas.groups import GroupCreateResponse, GroupItemResponse


router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post("/create", response_model=GroupCreateResponse)
def create_prediction_groups(
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    averages = group_predictions(session=session, slate=slate)

    return GroupCreateResponse(
        slate=slate,
        group_averages=averages,
    )


@router.get("", response_model=list[GroupItemResponse])
def list_prediction_groups(
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    query = text(
        """
        SELECT
            pgi.group_name,
            pgi.prediction_id,
            p.match_id,
            m.home_team,
            m.away_team,
            p.market,
            p.predicted_label,
            p.confidence
        FROM prediction_group_items pgi
        JOIN predictions p ON p.id = pgi.prediction_id
        JOIN matches m ON m.id = p.match_id
        WHERE pgi.slate = :slate
        ORDER BY pgi.group_name ASC, p.confidence DESC
        """
    )

    rows = session.execute(query, {"slate": slate}).mappings().all()

    return [GroupItemResponse(**row) for row in rows]