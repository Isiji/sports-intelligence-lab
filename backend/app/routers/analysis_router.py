# backend/app/routers/analysis_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analysis.match_analysis import get_match_analysis
from app.db.session import get_session
from app.schemas.match_analysis import MatchAnalysisResponse
from app.utils.slate import resolve_slate


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
)


@router.get(
    "/match/{match_id}",
    response_model=MatchAnalysisResponse,
)
def analyze_match(
    match_id: int,
    slate: str | None = Query(None),
    session: Session = Depends(get_session),
):
    selected_slate = resolve_slate(slate)

    result = get_match_analysis(
        session=session,
        match_id=match_id,
        slate=selected_slate,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Match not found.",
        )

    return result