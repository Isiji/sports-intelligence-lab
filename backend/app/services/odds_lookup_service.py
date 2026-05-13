from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MatchOdds
from app.odds.canonical_markets import get_market_family


@dataclass(frozen=True)
class OddsLookupResult:
    odds: float | None
    bookmaker: str | None = None
    provider_market: str | None = None
    provider_selection: str | None = None
    retrieved_at: object | None = None
    match_quality: str = "none"


def _clean(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower().strip()
    value = value.replace("&", " and ")
    value = value.replace("/", " ")
    value = value.replace("-", " ")
    value = value.replace("_", " ")
    value = re.sub(r"[^a-z0-9.+ ]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _line_from_key(key: str) -> str | None:
    match = re.search(r"(\d+_\d+)", key)
    if not match:
        return None
    return match.group(1).replace("_", ".")


def _signed_line_from_key(key: str) -> str | None:
    if "minus_" in key:
        part = key.split("minus_", 1)[1]
        return "-" + part.replace("_", ".")
    if "plus_" in key:
        part = key.split("plus_", 1)[1]
        return "+" + part.replace("_", ".")
    if key.endswith("_zero") or key.endswith("_0_0"):
        return "0.0"
    return None


def _contains_line(text: str, line: str | None) -> bool:
    if not line:
        return True

    variants = {
        line,
        line.replace(".0", ""),
        line.replace(".", ","),
        line.replace("+", ""),
    }

    return any(v in text for v in variants)


def _row_to_result(row: MatchOdds, quality: str) -> OddsLookupResult:
    return OddsLookupResult(
        odds=float(row.odds) if row.odds is not None else None,
        bookmaker=getattr(row, "bookmaker", None),
        provider_market=getattr(row, "market", None),
        provider_selection=getattr(row, "selection", None),
        retrieved_at=getattr(row, "retrieved_at", None),
        match_quality=quality,
    )


def _get_rows(session: Session, match_id: int) -> list[MatchOdds]:
    return list(
        session.scalars(
            select(MatchOdds).where(MatchOdds.match_id == match_id)
        )
    )


def _selection_candidates(
    canonical_market: str,
    selection: str | None,
) -> set[str]:
    key = canonical_market.upper()
    candidates = {key, key.replace("_GOALS", "")}

    if selection:
        sel = selection.upper()
        candidates.add(sel)
        candidates.add(sel.replace("_GOALS", ""))
        candidates.add(f"{sel}_GOALS")

    if canonical_market.startswith("home_over_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("home_over_", "").replace("_goals", "").upper()
        candidates.update({f"HOME_OVER_{line}", f"HOME_OVER_{line}_GOALS"})

    if canonical_market.startswith("away_over_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("away_over_", "").replace("_goals", "").upper()
        candidates.update({f"AWAY_OVER_{line}", f"AWAY_OVER_{line}_GOALS"})

    if canonical_market.startswith("home_under_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("home_under_", "").replace("_goals", "").upper()
        candidates.update({f"HOME_UNDER_{line}", f"HOME_UNDER_{line}_GOALS"})

    if canonical_market.startswith("away_under_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("away_under_", "").replace("_goals", "").upper()
        candidates.update({f"AWAY_UNDER_{line}", f"AWAY_UNDER_{line}_GOALS"})

    return {c for c in candidates if c}


def _exact_canonical_lookup(
    session: Session,
    match_id: int,
    canonical_market: str,
    selection: str | None,
) -> OddsLookupResult | None:
    candidates = _selection_candidates(canonical_market, selection)
    lower_candidates = {c.lower() for c in candidates}

    row = session.scalar(
        select(MatchOdds)
        .where(MatchOdds.match_id == match_id)
        .where(func.lower(MatchOdds.market) == canonical_market.lower())
        .where(func.lower(MatchOdds.selection).in_(lower_candidates))
        .where(MatchOdds.odds.is_not(None))
        .order_by(MatchOdds.odds.desc())
    )

    if row:
        return _row_to_result(row, "exact_canonical")

    row = session.scalar(
        select(MatchOdds)
        .where(MatchOdds.match_id == match_id)
        .where(func.lower(MatchOdds.market) == canonical_market.lower())
        .where(MatchOdds.odds.is_not(None))
        .order_by(MatchOdds.odds.desc())
    )

    if row:
        return _row_to_result(row, "exact_market_fallback")

    return None


DIRECT_ODDS_LOOKUP_MAP: dict[str, list[tuple[str, str]]] = {
    "home_win": [("match winner", "home"), ("fulltime result", "home"), ("1x2", "home"), ("winner", "1")],
    "draw": [("match winner", "draw"), ("fulltime result", "draw"), ("1x2", "x")],
    "away_win": [("match winner", "away"), ("fulltime result", "away"), ("1x2", "away"), ("winner", "2")],
    "double_chance_1x": [("double chance", "home draw"), ("double chance", "1x")],
    "double_chance_x2": [("double chance", "draw away"), ("double chance", "x2")],
    "double_chance_12": [("double chance", "home away"), ("double chance", "12")],
    "btts_yes": [("both teams score", "yes"), ("btts", "yes")],
    "btts_no": [("both teams score", "no"), ("btts", "no")],
    "draw_no_bet_home": [("draw no bet", "home"), ("dnb", "home")],
    "draw_no_bet_away": [("draw no bet", "away"), ("dnb", "away")],
}


SELECTION_ALIASES: dict[str, set[str]] = {
    "home": {"home", "1", "home team"},
    "away": {"away", "2", "away team"},
    "draw": {"draw", "x"},
    "yes": {"yes", "y"},
    "no": {"no", "n"},
    "over": {"over", "o"},
    "under": {"under", "u"},
    "1x": {"1x", "home draw", "home or draw"},
    "x2": {"x2", "draw away", "draw or away"},
    "12": {
        "12",
        "home away",
        "home or away",
        "1 2",
        "1/2",
        "either team",
        "no draw",
    },
}


def _selection_matches(selection: str, expected: str) -> bool:
    selection = _clean(selection)
    expected = _clean(expected)
    aliases = {_clean(a) for a in SELECTION_ALIASES.get(expected, {expected})}
    return selection in aliases or expected in selection


def _direct_lookup(
    rows: Iterable[MatchOdds],
    canonical_market: str,
) -> OddsLookupResult | None:
    for market_alias, selection_alias in DIRECT_ODDS_LOOKUP_MAP.get(canonical_market, []):
        for row in rows:
            if row.odds is None:
                continue

            market = _clean(getattr(row, "market", ""))
            selection = _clean(getattr(row, "selection", ""))

            if market_alias in market:
                if _selection_matches(selection, selection_alias):
                    return _row_to_result(row, "direct")

                combined = f"{market} {selection}"

                if selection_alias == "12":
                    if any(
                        x in combined
                        for x in [
                            "1 2",
                            "1/2",
                            "no draw",
                            "either team",
                        ]
                    ):
                        return _row_to_result(row, "direct")

    return None


def find_best_odds(
    session: Session,
    match_id: int,
    market: str | None = None,
    selection: str | None = None,
    canonical_market: str | None = None,
) -> OddsLookupResult | None:
    canonical_market = canonical_market or market

    if not canonical_market:
        return None

    exact = _exact_canonical_lookup(
        session=session,
        match_id=match_id,
        canonical_market=canonical_market,
        selection=selection,
    )

    if exact:
        return exact

    rows = _get_rows(session, match_id)

    if not rows:
        return None

    direct = _direct_lookup(rows, canonical_market)

    if direct:
        return direct

    return None