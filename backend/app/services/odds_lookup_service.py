from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import MatchOdds


@dataclass(frozen=True)
class OddsLookupResult:
    odds: float | None
    lookup_market: str
    lookup_selection: str
    matched_market: str | None
    matched_selection: str | None
    rows_found: int
    reason: str


DIRECT_ODDS_LOOKUP_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("home_win", "HOME_WIN"): ("home_win", "HOME_WIN"),
    ("home_win", "NOT_HOME_WIN"): ("away_win", "AWAY_WIN"),

    ("away_win", "AWAY_WIN"): ("away_win", "AWAY_WIN"),
    ("away_win", "NOT_AWAY_WIN"): ("home_win", "HOME_WIN"),

    ("draw", "DRAW"): ("draw", "DRAW"),
    ("draw", "NOT_DRAW"): ("double_chance_12", "DOUBLE_CHANCE_12"),

    ("over_1_5_goals", "OVER_1_5"): ("over_1_5_goals", "OVER_1_5"),
    ("over_1_5_goals", "UNDER_1_5"): ("under_1_5_goals", "UNDER_1_5"),

    ("under_1_5_goals", "UNDER_1_5"): ("under_1_5_goals", "UNDER_1_5"),
    ("under_1_5_goals", "OVER_1_5"): ("over_1_5_goals", "OVER_1_5"),

    ("over_2_5_goals", "OVER_2_5"): ("over_2_5_goals", "OVER_2_5"),
    ("over_2_5_goals", "UNDER_2_5"): ("under_2_5_goals", "UNDER_2_5"),

    ("under_2_5_goals", "UNDER_2_5"): ("under_2_5_goals", "UNDER_2_5"),
    ("under_2_5_goals", "OVER_2_5"): ("over_2_5_goals", "OVER_2_5"),

    ("over_3_5_goals", "OVER_3_5"): ("over_3_5_goals", "OVER_3_5"),
    ("over_3_5_goals", "UNDER_3_5"): ("under_3_5_goals", "UNDER_3_5"),

    ("under_3_5_goals", "UNDER_3_5"): ("under_3_5_goals", "UNDER_3_5"),
    ("under_3_5_goals", "OVER_3_5"): ("over_3_5_goals", "OVER_3_5"),

    ("btts_yes", "BTTS_YES"): ("btts_yes", "BTTS_YES"),
    ("btts_yes", "BTTS_NO"): ("btts_no", "BTTS_NO"),

    ("btts_no", "BTTS_NO"): ("btts_no", "BTTS_NO"),
    ("btts_no", "BTTS_YES"): ("btts_yes", "BTTS_YES"),

    ("double_chance_x2", "DOUBLE_CHANCE_X2"): (
        "double_chance_x2",
        "DOUBLE_CHANCE_X2",
    ),
    ("double_chance_x2", "NOT_DOUBLE_CHANCE_X2"): (
        "home_win",
        "HOME_WIN",
    ),

    ("double_chance_1x", "DOUBLE_CHANCE_1X"): (
        "double_chance_1x",
        "DOUBLE_CHANCE_1X",
    ),
    ("double_chance_1x", "NOT_DOUBLE_CHANCE_1X"): (
        "away_win",
        "AWAY_WIN",
    ),

    ("double_chance_12", "DOUBLE_CHANCE_12"): (
        "double_chance_12",
        "DOUBLE_CHANCE_12",
    ),
    ("double_chance_12", "NOT_DOUBLE_CHANCE_12"): (
        "draw",
        "DRAW",
    ),
}


SELECTION_ALIASES: dict[str, list[str]] = {
    "HOME_WIN": ["HOME_WIN", "HOME", "1"],
    "AWAY_WIN": ["AWAY_WIN", "AWAY", "2"],
    "DRAW": ["DRAW", "X"],

    "OVER_1_5": ["OVER_1_5", "OVER 1.5", "O1.5"],
    "UNDER_1_5": ["UNDER_1_5", "UNDER 1.5", "U1.5"],

    "OVER_2_5": ["OVER_2_5", "OVER 2.5", "O2.5"],
    "UNDER_2_5": ["UNDER_2_5", "UNDER 2.5", "U2.5"],

    "OVER_3_5": ["OVER_3_5", "OVER 3.5", "O3.5"],
    "UNDER_3_5": ["UNDER_3_5", "UNDER 3.5", "U3.5"],

    "BTTS_YES": ["BTTS_YES", "YES"],
    "BTTS_NO": ["BTTS_NO", "NO"],

    "DOUBLE_CHANCE_1X": ["DOUBLE_CHANCE_1X", "1X"],
    "DOUBLE_CHANCE_X2": ["DOUBLE_CHANCE_X2", "X2"],
    "DOUBLE_CHANCE_12": ["DOUBLE_CHANCE_12", "12"],
}


def find_best_odds(
    *,
    session: Session,
    match_id: int,
    market: str,
    selection: str,
    debug: bool = True,
) -> OddsLookupResult:
    lookup_market, lookup_selection = DIRECT_ODDS_LOOKUP_MAP.get(
        (market, selection),
        (market, selection),
    )

    candidate_selections = SELECTION_ALIASES.get(
        lookup_selection,
        [lookup_selection],
    )

    rows = (
        session.query(MatchOdds)
        .filter(
            MatchOdds.match_id == match_id,
            MatchOdds.market == lookup_market,
            MatchOdds.selection.in_(candidate_selections),
        )
        .order_by(
            MatchOdds.retrieved_at.desc(),
            MatchOdds.id.desc(),
        )
        .all()
    )

    if not rows:
        if debug:
            available = _available_markets_for_match(
                session=session,
                match_id=match_id,
            )

            print(
                "[ODDS MISS]",
                f"prediction_market={market}",
                f"prediction_selection={selection}",
                f"lookup_market={lookup_market}",
                f"lookup_selection={lookup_selection}",
                f"match_id={match_id}",
                f"available_markets={available[:12]}",
            )

        return OddsLookupResult(
            odds=None,
            lookup_market=lookup_market,
            lookup_selection=lookup_selection,
            matched_market=None,
            matched_selection=None,
            rows_found=0,
            reason="No matching odds rows found.",
        )

    valid_rows: list[tuple[float, MatchOdds]] = []

    for row in rows:
        try:
            odds_value = float(row.odds)
        except Exception:
            continue

        if odds_value <= 1.01:
            continue

        if odds_value > 100:
            continue

        valid_rows.append((odds_value, row))

    if not valid_rows:
        if debug:
            print(
                "[ODDS INVALID]",
                f"prediction_market={market}",
                f"prediction_selection={selection}",
                f"lookup_market={lookup_market}",
                f"lookup_selection={lookup_selection}",
                f"match_id={match_id}",
                f"rows_found={len(rows)}",
            )

        return OddsLookupResult(
            odds=None,
            lookup_market=lookup_market,
            lookup_selection=lookup_selection,
            matched_market=None,
            matched_selection=None,
            rows_found=len(rows),
            reason="Rows found, but no valid odds value.",
        )

    selected_odds, selected_row = max(
        valid_rows,
        key=lambda item: item[0],
    )

    return OddsLookupResult(
        odds=round(selected_odds, 4),
        lookup_market=lookup_market,
        lookup_selection=lookup_selection,
        matched_market=selected_row.market,
        matched_selection=selected_row.selection,
        rows_found=len(rows),
        reason="Matched odds successfully.",
    )


def _available_markets_for_match(
    *,
    session: Session,
    match_id: int,
) -> list[str]:
    rows = (
        session.query(MatchOdds.market)
        .filter(MatchOdds.match_id == match_id)
        .distinct()
        .limit(40)
        .all()
    )

    return sorted(
        str(row[0])
        for row in rows
        if row and row[0]
    )