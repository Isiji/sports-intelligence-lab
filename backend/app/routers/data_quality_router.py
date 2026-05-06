# backend/app/routers/data_quality_router.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analysis.data_quality import training_readiness_report
from app.db.session import get_session


router = APIRouter(
    prefix="/data-quality",
    tags=["Data Quality"],
)


@router.get("/training-readiness")
def training_readiness(
    session: Session = Depends(get_session),
):
    return training_readiness_report(session=session)