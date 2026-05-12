# backend/app/services/odds_lookup_service.py

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
    },}


def _selection_matches(selection: str, expected: str) -> bool:
    selection = _clean(selection)
    expected = _clean(expected)
    aliases = {_clean(a) for a in SELECTION_ALIASES.get(expected, {expected})}
    return selection in aliases or expected in selection


def _direct_lookup(rows: Iterable[MatchOdds], canonical_market: str) -> OddsLookupResult | None:
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


def _goal_total_lookup(rows: Iterable[MatchOdds], canonical_market: str) -> OddsLookupResult | None:
    line = _line_from_key(canonical_market)
    wants_over = canonical_market.startswith("over_")
    wants_under = canonical_market.startswith("under_")

    for row in rows:
        if row.odds is None:
            continue

        market = _clean(getattr(row, "market", ""))
        selection = _clean(getattr(row, "selection", ""))
        combined = f"{market} {selection}"

        if "goal" not in combined and "total" not in combined:
            continue

        if not _contains_line(combined, line):
            continue

        if wants_over and "over" in combined:
            return _row_to_result(row, "goal_total")

        if wants_under and "under" in combined:
            return _row_to_result(row, "goal_total")

    return None


def _team_total_lookup(rows: Iterable[MatchOdds], canonical_market: str) -> OddsLookupResult | None:
    line = _line_from_key(canonical_market)
    side = "home" if canonical_market.startswith("home_") else "away"
    wants_over = "_over_" in canonical_market
    wants_under = "_under_" in canonical_market

    side_aliases = {
        "home": ["home", "home team", "team 1"],
        "away": ["away", "away team", "team 2"],
    }

    for row in rows:
        if row.odds is None:
            continue

        market = _clean(getattr(row, "market", ""))
        selection = _clean(getattr(row, "selection", ""))
        combined = f"{market} {selection}"

        if not any(word in combined for word in ["team total", "home total", "away total", "home goals", "away goals"]):
            continue

        if not any(alias in combined for alias in side_aliases[side]):
            continue

        if not _contains_line(combined, line):
            continue

        if wants_over and "over" in combined:
            return _row_to_result(row, "team_total")

        if wants_under and "under" in combined:
            return _row_to_result(row, "team_total")

    return None


def _corners_lookup(rows: Iterable[MatchOdds], canonical_market: str) -> OddsLookupResult | None:
    line = _line_from_key(canonical_market)
    wants_over = "_over_" in canonical_market
    wants_under = "_under_" in canonical_market

    for row in rows:
        if row.odds is None:
            continue

        combined = f"{_clean(getattr(row, 'market', ''))} {_clean(getattr(row, 'selection', ''))}"

        if "corner" not in combined:
            continue

        if not _contains_line(combined, line):
            continue

        if wants_over and "over" in combined:
            return _row_to_result(row, "corners")

        if wants_under and "under" in combined:
            return _row_to_result(row, "corners")

    return None


def _shots_on_target_lookup(rows: Iterable[MatchOdds], canonical_market: str) -> OddsLookupResult | None:
    line = _line_from_key(canonical_market)
    wants_over = "_over_" in canonical_market
    wants_under = "_under_" in canonical_market

    for row in rows:
        if row.odds is None:
            continue

        combined = f"{_clean(getattr(row, 'market', ''))} {_clean(getattr(row, 'selection', ''))}"

        if "shot" not in combined or "target" not in combined:
            continue

        if not _contains_line(combined, line):
            continue

        if wants_over and "over" in combined:
            return _row_to_result(row, "shots_on_target")

        if wants_under and "under" in combined:
            return _row_to_result(row, "shots_on_target")

    return None


def _first_half_lookup(rows: Iterable[MatchOdds], canonical_market: str) -> OddsLookupResult | None:
    line = _line_from_key(canonical_market)

    for row in rows:
        if row.odds is None:
            continue

        market = _clean(getattr(row, "market", ""))
        selection = _clean(getattr(row, "selection", ""))
        combined = f"{market} {selection}"

        if "first half" not in combined and "1st half" not in combined and "half time" not in combined:
            continue

        if "home_win" in canonical_market and _selection_matches(selection, "home"):
            return _row_to_result(row, "first_half")

        if canonical_market.endswith("_draw") and _selection_matches(selection, "draw"):
            return _row_to_result(row, "first_half")

        if "away_win" in canonical_market and _selection_matches(selection, "away"):
            return _row_to_result(row, "first_half")

        if line and not _contains_line(combined, line):
            continue

        if "_over_" in canonical_market and "over" in combined:
            return _row_to_result(row, "first_half")

        if "_under_" in canonical_market and "under" in combined:
            return _row_to_result(row, "first_half")

    return None


def _asian_handicap_lookup(rows: Iterable[MatchOdds], canonical_market: str) -> OddsLookupResult | None:
    line = _signed_line_from_key(canonical_market)
    side = "home" if "_home_" in canonical_market else "away"

    for row in rows:
        if row.odds is None:
            continue

        market = _clean(getattr(row, "market", ""))
        selection = _clean(getattr(row, "selection", ""))
        combined = f"{market} {selection}"

        if "handicap" not in combined:
            continue

        if line and not _contains_line(combined, line):
            continue

        if side == "home" and _selection_matches(selection, "home"):
            return _row_to_result(row, "asian_handicap")

        if side == "away" and _selection_matches(selection, "away"):
            return _row_to_result(row, "asian_handicap")

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

    # IMPORTANT:
    # Do not rely only on get_market_family().
    # Some new/advanced markets may have family naming drift.
    fallback_lookups = [
        _goal_total_lookup,
        _team_total_lookup,
        _corners_lookup,
        _shots_on_target_lookup,
        _first_half_lookup,
        _asian_handicap_lookup,
    ]

    for lookup in fallback_lookups:
        result = lookup(rows, canonical_market)
        if result:
            return result

    return None