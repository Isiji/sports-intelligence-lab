# backend/app/odds/odds_matcher.py

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.odds.market_normalizer import normalize_market_and_selection
from app.odds.production_label_resolver import (
    LABEL_TO_MARKET,
    resolve_executable_market,
)


def find_best_odds_for_prediction(
    session: Session,
    match_id: int,
    target_market: str,
    predicted_label: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict:
    executable_market = resolve_executable_market(
        target_market=target_market,
        predicted_label=predicted_label,
    )

    executable_selection = _resolve_executable_selection(
        predicted_label=predicted_label,
        executable_market=executable_market,
    )

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

        normalized_market = normalized.canonical_market

        normalized_selection = (
            str(selection_name).upper().strip()
            if selection_name
            else None
        )

        diagnostic = {
            "raw_market": market_name,
            "raw_selection": selection_name,
            "normalized_market": normalized_market,
            "normalized_selection": normalized_selection,
            "reason": normalized.reason,
            "confidence": normalized.confidence,
            "odds": float(odds_value) if odds_value is not None else None,
            "bookmaker": row.get("bookmaker"),
            "provider": row.get("provider"),
            "retrieved_at": row.get("retrieved_at"),
        }

        diagnostics.append(diagnostic)

        if odds_value is None:
            continue

        if normalized_market != executable_market:
            continue

        if executable_selection:
            if normalized_selection != executable_selection:
                continue

        diagnostic["match_quality"] = "exact_executable_market"

        matches.append(diagnostic)

    if not matches:
        return {
            "matched": False,
            "reason": "no_matching_executable_market",
            "target_market": target_market,
            "predicted_label": predicted_label,
            "executable_market": executable_market,
            "executable_selection": executable_selection,
            "odds": None,
            "diagnostics": diagnostics[:40],
        }

    best = max(matches, key=lambda item: item["odds"] or 0)

    return {
        "matched": True,
        "reason": "exact_executable_market",
        "target_market": target_market,
        "predicted_label": predicted_label,
        "executable_market": executable_market,
        "executable_selection": executable_selection,
        "odds": best["odds"],
        "bookmaker": best["bookmaker"],
        "provider": best["provider"],
        "retrieved_at": best["retrieved_at"],
        "raw_market": best["raw_market"],
        "raw_selection": best["raw_selection"],
        "odds_market": executable_market,
        "odds_selection": executable_selection,
        "match_quality": "exact_executable_market",
        "diagnostics": diagnostics[:40],
    }


def _resolve_executable_selection(
    predicted_label: str | None,
    executable_market: str,
) -> str | None:
    if not predicted_label:
        return None

    label = predicted_label.upper().strip()

    if label.startswith("NOT_"):
        positive_label = label.replace("NOT_", "", 1)

        inverse_market = LABEL_TO_MARKET.get(positive_label)

        if inverse_market:
            return inverse_market.upper()

    if label.startswith("ASIAN_HANDICAP_"):
        return label

    if label.startswith("NOT_ASIAN_HANDICAP_"):
        return (
            executable_market.upper()
        )

    if label in LABEL_TO_MARKET:
        return executable_market.upper()

    return executable_market.upper()