from sqlalchemy import text
from sqlalchemy.orm import Session

from app.odds.market_normalizer import normalize_market_and_selection


def find_best_odds_for_prediction(
    session: Session,
    match_id: int,
    target_market: str,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict:
    rows = session.execute(
        text(
            """
            SELECT *
            FROM match_odds
            WHERE match_id = :match_id
            """
        ),
        {"match_id": match_id},
    ).mappings().all()

    if not rows:
        return {
            "matched": False,
            "reason": "missing_match_odds",
            "odds": None,
            "diagnostics": [],
        }

    diagnostics = []
    matches = []

    for row in rows:
        market_name = row.get("market") or row.get("market_name")
        selection_name = (
            row.get("selection")
            or row.get("selection_name")
            or row.get("label")
            or row.get("name")
        )

        odds_value = row.get("odds") or row.get("odd") or row.get("value")

        normalized = normalize_market_and_selection(
            market_name=market_name,
            selection_name=selection_name,
            home_team=home_team,
            away_team=away_team,
        )

        diagnostic = {
            "raw_market": market_name,
            "raw_selection": selection_name,
            "normalized_market": normalized.canonical_market,
            "reason": normalized.reason,
            "odds": float(odds_value) if odds_value is not None else None,
        }

        diagnostics.append(diagnostic)

        if normalized.canonical_market == target_market and odds_value is not None:
            matches.append(diagnostic)

    if not matches:
        return {
            "matched": False,
            "reason": "no_matching_canonical_market",
            "odds": None,
            "diagnostics": diagnostics[:30],
        }

    best = max(matches, key=lambda item: item["odds"] or 0)

    return {
        "matched": True,
        "reason": "matched",
        "odds": best["odds"],
        "raw_market": best["raw_market"],
        "raw_selection": best["raw_selection"],
        "diagnostics": diagnostics[:30],
    }