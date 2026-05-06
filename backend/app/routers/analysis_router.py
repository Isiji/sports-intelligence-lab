# backend/app/routers/analysis_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analysis.match_analysis import get_match_analysis
from app.db.session import get_session
from app.schemas.match_analysis import MatchAnalysisResponse


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
    slate: str = Query("demo"),
    session: Session = Depends(get_session),
):
    result = get_match_analysis(
        session=session,
        match_id=match_id,
        slate=slate,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Match not found.",
        )

    return result