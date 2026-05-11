# backend/app/api/routes/production.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.production_review_service import get_production_review

router = APIRouter(
    prefix="/production",
    tags=["Production Intelligence"],
)


@router.get("/review")
def production_review(
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    return get_production_review(
        session=db,
        slate=slate,
    )


@router.get("/summary")
def production_summary(
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    review = get_production_review(session=db, slate=slate)

    return {
        "slate": review["slate"],
        "prediction_summary": review["prediction_summary"],
        "markets_count": len(review["market_summary"]),
        "leagues_count": len(review["league_summary"]),
        "ranked_picks_count": len(review["ranked_picks"]),
        "best_picks_count": len(review["best_picks_per_match"]),
        "group_items_count": len(review["group_items"]),
    }


@router.get("/ranked-picks")
def ranked_picks(
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    review = get_production_review(session=db, slate=slate)
    return {
        "slate": review["slate"],
        "ranked_picks": review["ranked_picks"],
    }


@router.get("/best-picks")
def best_picks(
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    review = get_production_review(session=db, slate=slate)
    return {
        "slate": review["slate"],
        "best_picks_per_match": review["best_picks_per_match"],
    }


@router.get("/market-summary")
def market_summary(
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    review = get_production_review(session=db, slate=slate)
    return {
        "slate": review["slate"],
        "market_summary": review["market_summary"],
    }


@router.get("/league-summary")
def league_summary(
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    review = get_production_review(session=db, slate=slate)
    return {
        "slate": review["slate"],
        "league_summary": review["league_summary"],
    }


@router.get("/groups")
def production_groups(
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    review = get_production_review(session=db, slate=slate)
    return {
        "slate": review["slate"],
        "group_items": review["group_items"],
    }