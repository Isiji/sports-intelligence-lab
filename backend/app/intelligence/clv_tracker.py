# backend/app/intelligence/clv_tracker.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ClosingOddsResult:
    closing_odds: float | None
    opening_odds: float | None
    clv: float | None
    bookmaker: str | None
    market: str | None
    selection: str | None
    retrieved_at: datetime | None
    source: str
    reason: str


def resolve_closing_odds(
    *,
    session: Session,
    match_id: int,
    opening_odds: float | None,
    odds_bookmaker: str | None,
    odds_market: str | None,
    odds_selection: str | None,
    kickoff_datetime: datetime | None = None,
) -> ClosingOddsResult:
    if opening_odds is None or opening_odds <= 0:
        return _empty_result(
            opening_odds=opening_odds,
            reason="missing_or_invalid_opening_odds",
        )

    if not odds_market or not odds_selection:
        return _empty_result(
            opening_odds=opening_odds,
            reason="missing_market_or_selection",
        )

    row = _find_best_closing_odds_row(
        session=session,
        match_id=match_id,
        bookmaker=odds_bookmaker,
        market=odds_market,
        selection=odds_selection,
        kickoff_datetime=kickoff_datetime,
    )

    if not row:
        return _empty_result(
            opening_odds=opening_odds,
            reason="closing_odds_not_found",
        )

    closing_odds = _safe_float(row.get("odds"))

    if closing_odds is None or closing_odds <= 0:
        return _empty_result(
            opening_odds=opening_odds,
            reason="invalid_closing_odds",
        )

    return ClosingOddsResult(
        closing_odds=closing_odds,
        opening_odds=float(opening_odds),
        clv=calculate_clv(
            opening_odds=float(opening_odds),
            closing_odds=closing_odds,
        ),
        bookmaker=row.get("bookmaker"),
        market=row.get("market"),
        selection=row.get("selection"),
        retrieved_at=row.get("retrieved_at"),
        source="match_odds",
        reason="closing_odds_resolved",
    )


def _find_best_closing_odds_row(
    *,
    session: Session,
    match_id: int,
    bookmaker: str | None,
    market: str,
    selection: str,
    kickoff_datetime: datetime | None,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {
        "match_id": match_id,
        "market": market,
        "selection": selection,
        "bookmaker": bookmaker,
    }

    kickoff_filter = ""

    if kickoff_datetime is not None:
        params["kickoff_datetime"] = kickoff_datetime
        kickoff_filter = """
            AND (
                retrieved_at IS NULL
                OR retrieved_at <= :kickoff_datetime
            )
        """

    bookmaker_filter = ""

    if bookmaker:
        bookmaker_filter = """
            AND bookmaker = :bookmaker
        """

    row = session.execute(
        text(
            f"""
            SELECT
                bookmaker,
                market,
                selection,
                odds,
                retrieved_at
            FROM match_odds
            WHERE match_id = :match_id
              AND market = :market
              AND selection = :selection
              {bookmaker_filter}
              {kickoff_filter}
            ORDER BY
                retrieved_at DESC NULLS LAST,
                id DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()

    if row:
        return dict(row)

    fallback_row = session.execute(
        text(
            f"""
            SELECT
                bookmaker,
                market,
                selection,
                odds,
                retrieved_at
            FROM match_odds
            WHERE match_id = :match_id
              AND market = :market
              AND selection = :selection
              {kickoff_filter}
            ORDER BY
                retrieved_at DESC NULLS LAST,
                odds DESC,
                id DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()

    return dict(fallback_row) if fallback_row else None


def calculate_clv(
    *,
    opening_odds: float | None,
    closing_odds: float | None,
) -> float | None:
    if opening_odds is None or closing_odds is None:
        return None

    opening_odds = float(opening_odds)
    closing_odds = float(closing_odds)

    if opening_odds <= 0:
        return None

    return round(
        (closing_odds - opening_odds) / opening_odds,
        6,
    )


def _empty_result(
    *,
    opening_odds: float | None,
    reason: str,
) -> ClosingOddsResult:
    return ClosingOddsResult(
        closing_odds=None,
        opening_odds=opening_odds,
        clv=None,
        bookmaker=None,
        market=None,
        selection=None,
        retrieved_at=None,
        source="none",
        reason=reason,
    )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None