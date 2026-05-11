# backend/app/api/routes/production.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.production_review_service import (
    get_production_review,
)

router = APIRouter(
    prefix="/production",
    tags=["Production Intelligence"],
)


@router.get("/review")
def production_review(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )


@router.get("/summary")
def production_summary(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
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
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "ranked_picks": review["ranked_picks"],
    }


@router.get("/best-picks")
def best_picks(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "best_picks_per_match": review["best_picks_per_match"],
    }


@router.get("/market-summary")
def market_summary(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "market_summary": review["market_summary"],
    }


@router.get("/league-summary")
def league_summary(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "league_summary": review["league_summary"],
    }


@router.get("/groups")
def production_groups(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "group_items": review["group_items"],
    }
    
@router.get("/approved-picks")
def approved_picks(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "approved_picks": review["recommendations"]["approved_picks"],
        "summary": review["recommendations"]["recommendation_summary"],
    }


@router.get("/watchlist-picks")
def watchlist_picks(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "watchlist_picks": review["recommendations"]["watchlist_picks"],
        "summary": review["recommendations"]["recommendation_summary"],
    }


@router.get("/rejected-picks")
def rejected_picks(
    slate: str | None = None,
    market: str | None = None,
    league: str | None = None,
    require_odds: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        market=market,
        league=league,
        require_odds=require_odds,
        limit=limit,
    )

    return {
        "slate": review["slate"],
        "filters": review["filters"],
        "rejected_picks": review["recommendations"]["rejected_picks"],
        "summary": review["recommendations"]["recommendation_summary"],
    }


@router.get("/game-search")
def game_search(
    q: str,
    slate: str | None = None,
    db: Session = Depends(get_db),
):
    review = get_production_review(
        session=db,
        slate=slate,
        limit=1000,
    )

    query = q.lower().strip()

    matching_picks = [
        pick
        for pick in review["ranked_picks"]
        if query in str(pick.get("home_team", "")).lower()
        or query in str(pick.get("away_team", "")).lower()
        or query in str(pick.get("league", "")).lower()
    ]

    matching_best = [
        pick
        for pick in review["best_picks_per_match"]
        if query in str(pick.get("home_team", "")).lower()
        or query in str(pick.get("away_team", "")).lower()
        or query in str(pick.get("league", "")).lower()
    ]

    return {
        "slate": review["slate"],
        "query": q,
        "matches_found": len({pick["match_id"] for pick in matching_picks}),
        "best_picks": matching_best,
        "available_market_picks": matching_picks,
    }