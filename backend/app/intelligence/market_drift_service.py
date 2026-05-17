# backend/app/intelligence/market_drift_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


STEAM_MOVE_THRESHOLD = 0.08
HIGH_VOLATILITY_THRESHOLD = 0.12
LAST_MINUTE_WINDOW_MINUTES = 30


@dataclass(frozen=True)
class MarketDriftResult:
    match_id: int
    market: str
    selection: str

    opening_odds: float | None
    latest_odds: float | None

    best_closing_odds: float | None
    worst_closing_odds: float | None
    average_closing_odds: float | None

    bookmaker_count: int

    spread: float | None
    volatility: float | None
    line_range: float | None

    drift_direction: str | None
    drift_velocity: float | None

    opening_timestamp: datetime | None
    latest_timestamp: datetime | None

    last_minute_drift: float | None

    steam_move_detected: bool
    reverse_line_movement: bool
    high_volatility_market: bool
    sharp_consensus: bool

    reason: str


def analyze_market_drift(
    *,
    session: Session,
    match_id: int,
    market: str,
    selection: str,
    kickoff_datetime: datetime | None = None,
) -> MarketDriftResult:
    rows = (
        session.execute(
            text(
                """
                SELECT
                    bookmaker,
                    odds,
                    retrieved_at
                FROM match_odds
                WHERE match_id = :match_id
                  AND market = :market
                  AND selection = :selection
                ORDER BY retrieved_at ASC NULLS LAST, id ASC
                """
            ),
            {
                "match_id": match_id,
                "market": market,
                "selection": selection,
            },
        )
        .mappings()
        .all()
    )

    if not rows:
        return _empty_result(
            match_id=match_id,
            market=market,
            selection=selection,
            reason="no_market_odds_found",
        )

    cleaned_rows = []

    for row in rows:
        odds = _safe_float(row.get("odds"))

        if odds is None or odds <= 0:
            continue

        cleaned_rows.append(
            {
                "bookmaker": row.get("bookmaker"),
                "odds": odds,
                "retrieved_at": row.get("retrieved_at"),
            }
        )

    if not cleaned_rows:
        return _empty_result(
            match_id=match_id,
            market=market,
            selection=selection,
            reason="no_valid_odds_rows",
        )

    opening = cleaned_rows[0]
    latest = cleaned_rows[-1]

    odds_values = [
        row["odds"]
        for row in cleaned_rows
    ]

    opening_odds = opening["odds"]
    latest_odds = latest["odds"]

    best_closing_odds = max(odds_values)
    worst_closing_odds = min(odds_values)

    average_closing_odds = round(
        mean(odds_values),
        4,
    )

    spread = round(
        best_closing_odds - worst_closing_odds,
        4,
    )

    volatility = (
        round(pstdev(odds_values), 6)
        if len(odds_values) > 1
        else 0.0
    )

    line_range = spread

    bookmaker_count = len(
        {
            row["bookmaker"]
            for row in cleaned_rows
            if row["bookmaker"]
        }
    )

    drift_velocity = _calculate_drift_velocity(
        opening_odds=opening_odds,
        latest_odds=latest_odds,
        opening_timestamp=opening.get("retrieved_at"),
        latest_timestamp=latest.get("retrieved_at"),
    )

    drift_direction = _resolve_drift_direction(
        opening_odds=opening_odds,
        latest_odds=latest_odds,
    )

    last_minute_drift = _calculate_last_minute_drift(
        rows=cleaned_rows,
        kickoff_datetime=kickoff_datetime,
    )

    steam_move_detected = (
        abs(
            (latest_odds - opening_odds)
            / opening_odds
        ) >= STEAM_MOVE_THRESHOLD
    )

    reverse_line_movement = (
        opening_odds < average_closing_odds
        and latest_odds < opening_odds
    )

    high_volatility_market = (
        volatility >= HIGH_VOLATILITY_THRESHOLD
    )

    sharp_consensus = (
        spread <= 0.03
        and bookmaker_count >= 4
    )

    return MarketDriftResult(
        match_id=match_id,
        market=market,
        selection=selection,

        opening_odds=opening_odds,
        latest_odds=latest_odds,

        best_closing_odds=best_closing_odds,
        worst_closing_odds=worst_closing_odds,
        average_closing_odds=average_closing_odds,

        bookmaker_count=bookmaker_count,

        spread=spread,
        volatility=volatility,
        line_range=line_range,

        drift_direction=drift_direction,
        drift_velocity=drift_velocity,

        opening_timestamp=opening.get("retrieved_at"),
        latest_timestamp=latest.get("retrieved_at"),

        last_minute_drift=last_minute_drift,

        steam_move_detected=steam_move_detected,
        reverse_line_movement=reverse_line_movement,
        high_volatility_market=high_volatility_market,
        sharp_consensus=sharp_consensus,

        reason="market_drift_analyzed",
    )


def _calculate_drift_velocity(
    *,
    opening_odds: float,
    latest_odds: float,
    opening_timestamp: datetime | None,
    latest_timestamp: datetime | None,
) -> float | None:
    if (
        opening_timestamp is None
        or latest_timestamp is None
    ):
        return None

    seconds = (
        latest_timestamp - opening_timestamp
    ).total_seconds()

    if seconds <= 0:
        return None

    return round(
        (latest_odds - opening_odds) / seconds,
        8,
    )


def _resolve_drift_direction(
    *,
    opening_odds: float,
    latest_odds: float,
) -> str:
    if latest_odds > opening_odds:
        return "UP"

    if latest_odds < opening_odds:
        return "DOWN"

    return "FLAT"


def _calculate_last_minute_drift(
    *,
    rows: list[dict[str, Any]],
    kickoff_datetime: datetime | None,
) -> float | None:
    if kickoff_datetime is None:
        return None

    threshold = kickoff_datetime - timedelta(
        minutes=LAST_MINUTE_WINDOW_MINUTES
    )

    relevant = [
        row
        for row in rows
        if row.get("retrieved_at")
        and row["retrieved_at"] >= threshold
    ]

    if len(relevant) < 2:
        return None

    opening = relevant[0]["odds"]
    latest = relevant[-1]["odds"]

    if opening <= 0:
        return None

    return round(
        (latest - opening) / opening,
        6,
    )


def _empty_result(
    *,
    match_id: int,
    market: str,
    selection: str,
    reason: str,
) -> MarketDriftResult:
    return MarketDriftResult(
        match_id=match_id,
        market=market,
        selection=selection,

        opening_odds=None,
        latest_odds=None,

        best_closing_odds=None,
        worst_closing_odds=None,
        average_closing_odds=None,

        bookmaker_count=0,

        spread=None,
        volatility=None,
        line_range=None,

        drift_direction=None,
        drift_velocity=None,

        opening_timestamp=None,
        latest_timestamp=None,

        last_minute_drift=None,

        steam_move_detected=False,
        reverse_line_movement=False,
        high_volatility_market=False,
        sharp_consensus=False,

        reason=reason,
    )


def _safe_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None