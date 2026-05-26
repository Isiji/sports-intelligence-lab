# backend/app/services/odds_lookup_service.py

from __future__ import annotations

import re
from dataclasses import dataclass
from math import fabs
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MatchOdds
from app.odds.production_label_resolver import (
    resolve_execution_market_candidates,
    resolve_executable_market,
)


LOCAL_BOOKMAKERS = {
    "betika",
    "sportpesa",
    "sport pesa",
    "odibets",
    "odi bets",
    "mozzart",
    "mozzartbet",
    "mozzart bet",
}


LOCAL_BOOKMAKER_NORMALIZATION = {
    "betika": "Betika",
    "sportpesa": "SportPesa",
    "sport pesa": "SportPesa",
    "odibets": "Odibets",
    "odi bets": "Odibets",
    "mozzart": "Mozzart",
    "mozzartbet": "Mozzart",
    "mozzart bet": "Mozzart",
}


@dataclass(frozen=True)
class OddsLookupResult:
    odds: float | None
    bookmaker: str | None = None
    provider_market: str | None = None
    provider_selection: str | None = None
    retrieved_at: object | None = None
    match_quality: str = "none"

    executable_market: str | None = None
    executable_selection: str | None = None
    execution_family: str | None = None
    execution_line: float | None = None

    local_bookmaker: bool = False
    bookmaker_locality: str = "GLOBAL"
    local_realism_score: float = 0.0
    execution_score: float = 0.0
    execution_reasons: list[str] | None = None
    market_alternatives: list[dict[str, Any]] | None = None


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


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _normalize_bookmaker(bookmaker: str | None) -> str | None:
    if not bookmaker:
        return None

    key = _clean(bookmaker)

    return (
        LOCAL_BOOKMAKER_NORMALIZATION.get(key)
        or bookmaker.strip()
    )


def _is_local_bookmaker(bookmaker: str | None) -> bool:
    if not bookmaker:
        return False

    return _clean(bookmaker) in LOCAL_BOOKMAKERS


def _execution_family(market: str | None) -> str:
    key = (market or "").lower().strip()

    if key.startswith("asian_handicap_"):
        return "asian_handicap_directional"

    if key.startswith("handicap_result_"):
        return "handicap_result_3way"

    if key.startswith("result_total_"):
        return "result_total"

    if key.startswith("first_half_double_chance_"):
        return "first_half_double_chance"

    if key.startswith("first_half_"):
        return "first_half"

    if key.startswith("second_half_"):
        return "second_half"

    if key.startswith("home_over_") or key.startswith("home_under_"):
        return "home_team_total"

    if key.startswith("away_over_") or key.startswith("away_under_"):
        return "away_team_total"

    if key.startswith("corners_"):
        return "corners_total"

    if key.startswith("shots_on_target_"):
        return "shots_on_target_total"

    if key in {"home_win", "draw", "away_win"}:
        return "match_winner"

    if key.startswith("double_chance_"):
        return "double_chance"

    if key.startswith("draw_no_bet_"):
        return "draw_no_bet"

    if key.startswith("btts_"):
        return "btts"

    if "over" in key or "under" in key:
        return "goals_total"

    return "other"


def _line_from_key(key: str | None) -> float | None:
    if not key:
        return None

    key = key.lower()

    if "minus_" in key:
        raw = key.split("minus_", 1)[1]
        match = re.search(r"(\d+(?:_\d+)?)", raw)

        if not match:
            return None

        return -float(match.group(1).replace("_", "."))

    if "plus_" in key:
        raw = key.split("plus_", 1)[1]
        match = re.search(r"(\d+(?:_\d+)?)", raw)

        if not match:
            return None

        return float(match.group(1).replace("_", "."))

    if key.endswith("_0_0") or key.endswith("_zero"):
        return 0.0

    match = re.search(r"(\d+_\d+)", key)

    if not match:
        return None

    return float(match.group(1).replace("_", "."))


def _signed_line_text(key: str | None) -> str | None:
    line = _line_from_key(key)

    if line is None:
        return None

    if line > 0:
        return f"+{line:g}"

    return f"{line:g}"


def _contains_line(text: str, line: float | None) -> bool:
    if line is None:
        return True

    signed = f"{line:g}"
    unsigned = f"{abs(line):g}"

    variants = {
        signed,
        signed.replace(".", ","),
        unsigned,
        unsigned.replace(".", ","),
    }

    if line > 0:
        variants.add(f"+{unsigned}")

    if line < 0:
        variants.add(f"-{unsigned}")

    return any(v in text for v in variants)


def _selection_candidates(
    canonical_market: str,
    selection: str | None,
) -> set[str]:

    key = canonical_market.upper()

    candidates = {
        key,
        key.replace("_GOALS", ""),
    }

    if selection:
        sel = selection.upper()
        candidates.add(sel)
        candidates.add(sel.replace("_GOALS", ""))
        candidates.add(f"{sel}_GOALS")

    if canonical_market.startswith("home_over_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("home_over_", "").replace("_goals", "").upper()
        candidates.update(
            {
                f"HOME_OVER_{line}",
                f"HOME_OVER_{line}_GOALS",
                "HOME_OVER",
                "OVER",
            }
        )

    if canonical_market.startswith("away_over_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("away_over_", "").replace("_goals", "").upper()
        candidates.update(
            {
                f"AWAY_OVER_{line}",
                f"AWAY_OVER_{line}_GOALS",
                "AWAY_OVER",
                "OVER",
            }
        )

    if canonical_market.startswith("home_under_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("home_under_", "").replace("_goals", "").upper()
        candidates.update(
            {
                f"HOME_UNDER_{line}",
                f"HOME_UNDER_{line}_GOALS",
                "HOME_UNDER",
                "UNDER",
            }
        )

    if canonical_market.startswith("away_under_") and canonical_market.endswith("_goals"):
        line = canonical_market.replace("away_under_", "").replace("_goals", "").upper()
        candidates.update(
            {
                f"AWAY_UNDER_{line}",
                f"AWAY_UNDER_{line}_GOALS",
                "AWAY_UNDER",
                "UNDER",
            }
        )

    if canonical_market.startswith("asian_handicap_home_"):
        candidates.update(
            {
                "HOME",
                "1",
                "HANDICAP_HOME",
                "ASIAN_HANDICAP_HOME",
            }
        )

    if canonical_market.startswith("asian_handicap_away_"):
        candidates.update(
            {
                "AWAY",
                "2",
                "HANDICAP_AWAY",
                "ASIAN_HANDICAP_AWAY",
            }
        )

    return {
        c
        for c in candidates
        if c
    }


DIRECT_ODDS_LOOKUP_MAP: dict[str, list[tuple[str, str]]] = {
    "home_win": [
        ("match winner", "home"),
        ("fulltime result", "home"),
        ("full time result", "home"),
        ("1x2", "home"),
        ("winner", "1"),
    ],
    "draw": [
        ("match winner", "draw"),
        ("fulltime result", "draw"),
        ("full time result", "draw"),
        ("1x2", "x"),
    ],
    "away_win": [
        ("match winner", "away"),
        ("fulltime result", "away"),
        ("full time result", "away"),
        ("1x2", "away"),
        ("winner", "2"),
    ],
    "double_chance_1x": [
        ("double chance", "home draw"),
        ("double chance", "1x"),
    ],
    "double_chance_x2": [
        ("double chance", "draw away"),
        ("double chance", "x2"),
    ],
    "double_chance_12": [
        ("double chance", "home away"),
        ("double chance", "12"),
    ],
    "btts_yes": [
        ("both teams score", "yes"),
        ("both teams to score", "yes"),
        ("btts", "yes"),
    ],
    "btts_no": [
        ("both teams score", "no"),
        ("both teams to score", "no"),
        ("btts", "no"),
    ],
    "draw_no_bet_home": [
        ("draw no bet", "home"),
        ("dnb", "home"),
    ],
    "draw_no_bet_away": [
        ("draw no bet", "away"),
        ("dnb", "away"),
    ],
    "home_away_home": [
        ("home away", "home"),
        ("home/away", "home"),
    ],
    "home_away_away": [
        ("home away", "away"),
        ("home/away", "away"),
    ],
}

RESULT_TOTAL_MARKET_ALIASES: dict[str, list[tuple[str, str]]] = {
    "result_total_home_over_1_5_goals": [
        ("result total", "home and over 1.5"),
        ("win and over", "home over 1.5"),
        ("match combo", "home over 1.5"),
    ],

    "result_total_home_over_2_5_goals": [
        ("result total", "home and over 2.5"),
        ("win and over", "home over 2.5"),
        ("match combo", "home over 2.5"),
    ],

    "result_total_home_over_3_5_goals": [
        ("result total", "home and over 3.5"),
        ("win and over", "home over 3.5"),
        ("match combo", "home over 3.5"),
    ],

    "result_total_draw_over_1_5_goals": [
        ("result total", "draw and over 1.5"),
        ("match combo", "draw over 1.5"),
    ],

    "result_total_draw_over_2_5_goals": [
        ("result total", "draw and over 2.5"),
        ("match combo", "draw over 2.5"),
    ],

    "result_total_draw_over_3_5_goals": [
        ("result total", "draw and over 3.5"),
        ("match combo", "draw over 3.5"),
    ],

    "result_total_away_over_1_5_goals": [
        ("result total", "away and over 1.5"),
        ("win and over", "away over 1.5"),
        ("match combo", "away over 1.5"),
    ],

    "result_total_away_over_2_5_goals": [
        ("result total", "away and over 2.5"),
        ("win and over", "away over 2.5"),
        ("match combo", "away over 2.5"),
    ],

    "result_total_away_over_3_5_goals": [
        ("result total", "away and over 3.5"),
        ("win and over", "away over 3.5"),
        ("match combo", "away over 3.5"),
    ],
}

SELECTION_ALIASES: dict[str, set[str]] = {
    "home": {
        "home",
        "1",
        "home team",
    },
    "away": {
        "away",
        "2",
        "away team",
    },
    "draw": {
        "draw",
        "x",
    },
    "yes": {
        "yes",
        "y",
    },
    "no": {
        "no",
        "n",
    },
    "over": {
        "over",
        "o",
    },
    "under": {
        "under",
        "u",
    },
    "1x": {
        "1x",
        "home draw",
        "home or draw",
    },
    "x2": {
        "x2",
        "draw away",
        "draw or away",
    },
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


def _selection_matches(
    selection: str,
    expected: str,
) -> bool:

    selection_clean = _clean(selection)
    expected_clean = _clean(expected)

    aliases = {
        _clean(alias)
        for alias in SELECTION_ALIASES.get(
            expected_clean,
            {expected_clean},
        )
    }

    return (
        selection_clean in aliases
        or expected_clean in selection_clean
        or selection_clean in expected_clean
    )


def _row_to_result(
    row: MatchOdds,
    quality: str,
    *,
    executable_market: str,
    source_market: str,
    source_label: str | None,
    alternatives: list[dict[str, Any]] | None = None,
) -> OddsLookupResult:

    odds = _safe_float(
        getattr(row, "odds", None)
    )

    bookmaker = _normalize_bookmaker(
        getattr(row, "bookmaker", None)
    )

    raw_market = getattr(row, "market", None)
    raw_selection = getattr(row, "selection", None)

    execution_line = _line_from_key(
        executable_market
    )

    family = _execution_family(
        executable_market
    )

    local = _is_local_bookmaker(
        bookmaker
    )

    local_score = _local_realism_score(
        odds=odds,
        bookmaker=bookmaker,
        executable_market=executable_market,
        quality=quality,
    )

    execution_score, reasons = _execution_score(
        odds=odds,
        bookmaker=bookmaker,
        source_market=source_market,
        executable_market=executable_market,
        quality=quality,
        local_realism_score=local_score,
    )

    return OddsLookupResult(
        odds=odds,
        bookmaker=bookmaker,
        provider_market=raw_market,
        provider_selection=raw_selection,
        retrieved_at=getattr(row, "retrieved_at", None),
        match_quality=quality,
        executable_market=executable_market,
        executable_selection=raw_selection,
        execution_family=family,
        execution_line=execution_line,
        local_bookmaker=local,
        bookmaker_locality=(
            "LOCAL"
            if local
            else "GLOBAL"
        ),
        local_realism_score=local_score,
        execution_score=execution_score,
        execution_reasons=reasons,
        market_alternatives=alternatives or [],
    )


def _local_realism_score(
    *,
    odds: float | None,
    bookmaker: str | None,
    executable_market: str | None,
    quality: str,
) -> float:

    score = 0.0

    if _is_local_bookmaker(bookmaker):
        score += 0.42

    if quality in {
        "exact_executable_market",
        "exact_canonical",
    }:
        score += 0.22

    elif quality in {
        "asian_handicap_family_fallback",
        "execution_family_fallback",
    }:
        score += 0.14

    if odds is not None:
        odds_value = float(odds)

        if 1.25 <= odds_value <= 2.40:
            score += 0.28

        elif 2.40 < odds_value <= 3.20:
            score += 0.14

        elif odds_value > 4.00:
            score -= 0.18

        elif odds_value < 1.20:
            score -= 0.14

    family = _execution_family(
        executable_market
    )

    if family in {
        "match_winner",
        "double_chance",
        "draw_no_bet",
        "goals_total",
        "btts",
        "asian_handicap_directional",
        "home_team_total",
        "away_team_total",
    }:
        score += 0.08

    return round(
        max(0.0, min(score, 1.0)),
        4,
    )


def _execution_score(
    *,
    odds: float | None,
    bookmaker: str | None,
    source_market: str,
    executable_market: str,
    quality: str,
    local_realism_score: float,
) -> tuple[float, list[str]]:

    score = 0.0
    reasons: list[str] = []

    if quality == "exact_executable_market":
        score += 100.0
        reasons.append("exact executable market")

    elif quality == "exact_canonical":
        score += 88.0
        reasons.append("exact canonical odds")

    elif quality == "asian_handicap_family_fallback":
        score += 74.0
        reasons.append("nearby Asian handicap execution line")

    elif quality == "execution_family_fallback":
        score += 66.0
        reasons.append("same execution family fallback")

    elif quality == "direct":
        score += 58.0
        reasons.append("provider alias direct match")

    else:
        score += 24.0
        reasons.append("weak odds match")

    if _is_local_bookmaker(bookmaker):
        score += 18.0
        reasons.append("local Kenyan bookmaker")

    score += local_realism_score * 20.0

    odds_value = _safe_float(odds)

    if odds_value is not None:
        if 1.30 <= odds_value <= 2.20:
            score += 12.0
            reasons.append("strong executable odds band")

        elif 2.20 < odds_value <= 3.20:
            score += 5.0
            reasons.append("usable odds band")

        elif odds_value > 3.50:
            score -= 16.0
            reasons.append("high local execution risk")

        elif odds_value < 1.25:
            score -= 14.0
            reasons.append("too compressed odds")

    source_line = _line_from_key(
        source_market
    )

    execution_line = _line_from_key(
        executable_market
    )

    if (
        source_market.startswith("asian_handicap_")
        and executable_market.startswith("asian_handicap_")
        and source_line is not None
        and execution_line is not None
    ):
        distance = fabs(
            source_line - execution_line
        )

        if distance == 0:
            score += 10.0
            reasons.append("same handicap line")

        elif distance <= 0.25:
            score += 7.0
            reasons.append("very close handicap line")

        elif distance <= 0.75:
            score += 2.0
            reasons.append("acceptable handicap substitute")

        else:
            score -= 15.0
            reasons.append("far handicap substitute")

    return round(score, 4), reasons


def _get_rows(
    session: Session,
    match_id: int,
) -> list[MatchOdds]:

    return list(
        session.scalars(
            select(MatchOdds)
            .where(MatchOdds.match_id == match_id)
            .where(MatchOdds.odds.is_not(None))
        )
    )


def _exact_canonical_lookup(
    session: Session,
    match_id: int,
    canonical_market: str,
    selection: str | None,
    *,
    source_market: str,
    source_label: str | None,
) -> OddsLookupResult | None:

    candidates = _selection_candidates(
        canonical_market,
        selection,
    )

    lower_candidates = {
        c.lower()
        for c in candidates
    }

    row = session.scalar(
        select(MatchOdds)
        .where(MatchOdds.match_id == match_id)
        .where(func.lower(MatchOdds.market) == canonical_market.lower())
        .where(func.lower(MatchOdds.selection).in_(lower_candidates))
        .where(MatchOdds.odds.is_not(None))
        .order_by(
            MatchOdds.bookmaker.asc(),
            MatchOdds.odds.desc(),
        )
    )

    if row:
        return _row_to_result(
            row,
            "exact_executable_market",
            executable_market=canonical_market,
            source_market=source_market,
            source_label=source_label,
        )

    row = session.scalar(
        select(MatchOdds)
        .where(MatchOdds.match_id == match_id)
        .where(func.lower(MatchOdds.market) == canonical_market.lower())
        .where(MatchOdds.odds.is_not(None))
        .order_by(
            MatchOdds.bookmaker.asc(),
            MatchOdds.odds.desc(),
        )
    )

    if row:
        return _row_to_result(
            row,
            "exact_canonical",
            executable_market=canonical_market,
            source_market=source_market,
            source_label=source_label,
        )

    return None


def _direct_lookup(
    rows: Iterable[MatchOdds],
    canonical_market: str,
    *,
    source_market: str,
    source_label: str | None,
) -> OddsLookupResult | None:

    for market_alias, selection_alias in DIRECT_ODDS_LOOKUP_MAP.get(
        canonical_market,
        [],
    ):
        candidates: list[OddsLookupResult] = []

        for row in rows:

            if row.odds is None:
                continue

            market = _clean(
                getattr(row, "market", "")
            )

            selection = _clean(
                getattr(row, "selection", "")
            )

            if market_alias not in market:
                continue

            if _selection_matches(
                selection,
                selection_alias,
            ):
                candidates.append(
                    _row_to_result(
                        row,
                        "direct",
                        executable_market=canonical_market,
                        source_market=source_market,
                        source_label=source_label,
                    )
                )

                continue

            combined = f"{market} {selection}"

            if (
                selection_alias == "12"
                and any(
                    x in combined
                    for x in [
                        "1 2",
                        "1/2",
                        "no draw",
                        "either team",
                    ]
                )
            ):
                candidates.append(
                    _row_to_result(
                        row,
                        "direct",
                        executable_market=canonical_market,
                        source_market=source_market,
                        source_label=source_label,
                    )
                )

        if candidates:
            return _best_candidate(
                candidates
            )

    return None

def _result_total_lookup(
    rows: Iterable[MatchOdds],
    canonical_market: str,
    *,
    source_market: str,
    source_label: str | None,
) -> OddsLookupResult | None:

    aliases = RESULT_TOTAL_MARKET_ALIASES.get(
        canonical_market,
        []
    )

    if not aliases:
        return None

    candidates: list[OddsLookupResult] = []

    for market_alias, selection_alias in aliases:

        for row in rows:

            if row.odds is None:
                continue

            market = _clean(
                getattr(row, "market", "")
            )

            selection = _clean(
                getattr(row, "selection", "")
            )

            combined = f"{market} {selection}"

            if market_alias not in combined:
                continue

            selection_parts = [
                x.strip()
                for x in selection_alias.split()
            ]

            matched = sum(
                1
                for part in selection_parts
                if part in combined
            )

            if matched < max(
                2,
                len(selection_parts) // 2,
            ):
                continue

            candidates.append(
                _row_to_result(
                    row,
                    "execution_family_fallback",
                    executable_market=canonical_market,
                    source_market=source_market,
                    source_label=source_label,
                )
            )

    if not candidates:
        return None

    return _best_candidate(
        candidates
    )

def _asian_handicap_family_lookup(
    rows: Iterable[MatchOdds],
    executable_markets: list[str],
    *,
    source_market: str,
    source_label: str | None,
) -> OddsLookupResult | None:

    source_side = (
        "home"
        if "_home_" in source_market
        else (
            "away"
            if "_away_" in source_market
            else None
        )
    )

    candidates: list[OddsLookupResult] = []

    for executable_market in executable_markets:

        if not executable_market.startswith(
            "asian_handicap_"
        ):
            continue

        expected_line = _line_from_key(
            executable_market
        )

        expected_side = (
            "home"
            if "_home_" in executable_market
            else (
                "away"
                if "_away_" in executable_market
                else None
            )
        )

        if (
            source_side is not None
            and expected_side != source_side
        ):
            continue

        for row in rows:

            if row.odds is None:
                continue

            market_text = _clean(
                getattr(row, "market", "")
            )

            selection_text = _clean(
                getattr(row, "selection", "")
            )

            combined = (
                f"{market_text} {selection_text}"
            )

            if (
                "handicap" not in combined
                and "asian" not in combined
            ):
                continue

            if expected_side == "home":
                side_ok = any(
                    token in selection_text
                    for token in [
                        "home",
                        "1",
                    ]
                )

            elif expected_side == "away":
                side_ok = any(
                    token in selection_text
                    for token in [
                        "away",
                        "2",
                    ]
                )

            else:
                side_ok = True

            if not side_ok:
                continue

            if not _contains_line(
                combined,
                expected_line,
            ):
                continue

            candidates.append(
                _row_to_result(
                    row,
                    "asian_handicap_family_fallback",
                    executable_market=executable_market,
                    source_market=source_market,
                    source_label=source_label,
                )
            )

    if not candidates:
        return None

    return _best_candidate(
        candidates
    )


def _same_family_lookup(
    rows: Iterable[MatchOdds],
    executable_markets: list[str],
    *,
    source_market: str,
    source_label: str | None,
) -> OddsLookupResult | None:

    candidates: list[OddsLookupResult] = []

    for executable_market in executable_markets:

        family = _execution_family(
            executable_market
        )

        line = _line_from_key(
            executable_market
        )

        for row in rows:

            if row.odds is None:
                continue

            market_text = _clean(
                getattr(row, "market", "")
            )

            selection_text = _clean(
                getattr(row, "selection", "")
            )

            combined = (
                f"{market_text} {selection_text}"
            )

            if family == "goals_total":
                if not (
                    "total" in combined
                    or "goal" in combined
                    or "over" in combined
                    or "under" in combined
                ):
                    continue

                if not _contains_line(
                    combined,
                    line,
                ):
                    continue

            elif family in {
                "home_team_total",
                "away_team_total",
            }:
                side = (
                    "home"
                    if family == "home_team_total"
                    else "away"
                )

                if side not in combined:
                    continue

                if not _contains_line(
                    combined,
                    line,
                ):
                    continue

            else:
                continue

            candidates.append(
                _row_to_result(
                    row,
                    "execution_family_fallback",
                    executable_market=executable_market,
                    source_market=source_market,
                    source_label=source_label,
                )
            )

    if not candidates:
        return None

    return _best_candidate(
        candidates
    )


def _best_candidate(
    candidates: list[OddsLookupResult],
) -> OddsLookupResult | None:

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda item: (
            item.local_bookmaker is False,
            -float(item.execution_score or 0.0),
            -float(item.local_realism_score or 0.0),

            item.match_quality not in {
                "exact_executable_market",
                "exact_canonical",
            },

            float(item.odds or 999.0),
        ),
    )[0]

def _alternatives_from_candidates(
    candidates: list[OddsLookupResult],
) -> list[dict[str, Any]]:

    alternatives: list[dict[str, Any]] = []

    seen: set[tuple[str | None, str | None, str | None]] = set()

    for item in sorted(
        candidates,
        key=lambda row: (
            row.local_bookmaker is False,
            -float(row.execution_score or 0.0),
            -float(row.local_realism_score or 0.0),
            float(row.odds or 999.0),
        ),
    ):

        key = (
            item.executable_market,
            item.executable_selection,
            item.bookmaker,
        )

        if key in seen:
            continue

        seen.add(key)

        alternatives.append(
            {
                "execution_market": item.executable_market,
                "execution_selection": item.executable_selection,
                "bookmaker": item.bookmaker,
                "odds": item.odds,
                "match_quality": item.match_quality,
                "execution_family": item.execution_family,
                "execution_line": item.execution_line,
                "bookmaker_locality": item.bookmaker_locality,
                "local_realism_score": item.local_realism_score,
                "execution_score": item.execution_score,
                "execution_reasons": item.execution_reasons or [],
            }
        )

    return alternatives[:10]


def find_best_odds(
    session: Session,
    match_id: int,
    market: str | None = None,
    selection: str | None = None,
    canonical_market: str | None = None,
) -> OddsLookupResult | None:

    canonical_market = (
        canonical_market
        or market
    )

    if not canonical_market:
        return None

    exact = _exact_canonical_lookup(
        session=session,
        match_id=match_id,
        canonical_market=canonical_market,
        selection=selection,
        source_market=canonical_market,
        source_label=selection,
    )

    if exact:
        return exact

    rows = _get_rows(
        session=session,
        match_id=match_id,
    )

    if not rows:
        return None

    direct = _direct_lookup(
        rows,
        canonical_market,
        source_market=canonical_market,
        source_label=selection,
    )

    if direct:
        return direct

    return None


def find_best_odds_for_prediction(
    session: Session,
    match_id: int,
    target_market: str,
    predicted_label: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict[str, Any] | None:

    executable_market = resolve_executable_market(
        target_market=target_market,
        predicted_label=predicted_label,
    )

    executable_candidates = (
        resolve_execution_market_candidates(
            target_market=target_market,
            predicted_label=predicted_label,
        )
    )

    if executable_market not in executable_candidates:
        executable_candidates.insert(
            0,
            executable_market,
        )

    rows = _get_rows(
        session=session,
        match_id=match_id,
    )

    if not rows:
        return None

    all_candidates: list[OddsLookupResult] = []

    for candidate_market in executable_candidates:

        exact = _exact_canonical_lookup(
            session=session,
            match_id=match_id,
            canonical_market=candidate_market,
            selection=predicted_label,
            source_market=executable_market,
            source_label=predicted_label,
        )

        if exact:
            all_candidates.append(
                exact
            )

        direct = _direct_lookup(
            rows,
            candidate_market,
            source_market=executable_market,
            source_label=predicted_label,
        )

        result_total = _result_total_lookup(
            rows,
            candidate_market,
            source_market=executable_market,
            source_label=predicted_label,
        )

        if result_total:
            all_candidates.append(
                result_total
            )

        if direct:
            all_candidates.append(
                direct
            )

    asian_family = _asian_handicap_family_lookup(
        rows,
        executable_candidates,
        source_market=executable_market,
        source_label=predicted_label,
    )

    if asian_family:
        all_candidates.append(
            asian_family
        )

    same_family = _same_family_lookup(
        rows,
        executable_candidates,
        source_market=executable_market,
        source_label=predicted_label,
    )

    if same_family:
        all_candidates.append(
            same_family
        )

    if not all_candidates:
        return None

    alternatives = _alternatives_from_candidates(
        all_candidates
    )

    best = _best_candidate(
        all_candidates
    )

    if best is None:
        return None

    payload = {
        "odds": best.odds,
        "bookmaker": best.bookmaker,
        "odds_bookmaker": best.bookmaker,
        "market": best.provider_market,
        "selection": best.provider_selection,
        "odds_market": best.provider_market,
        "odds_selection": best.provider_selection,
        "retrieved_at": best.retrieved_at,
        "odds_retrieved_at": best.retrieved_at,
        "match_quality": best.match_quality,
        "odds_match_quality": best.match_quality,

        "executable_market": best.executable_market,
        "execution_market": best.executable_market,
        "executable_selection": best.executable_selection,
        "execution_selection": best.executable_selection,
        "execution_family": best.execution_family,
        "execution_line": best.execution_line,

        "bookmaker_locality": best.bookmaker_locality,
        "local_bookmaker": best.local_bookmaker,
        "local_realism_score": best.local_realism_score,
        "execution_score": best.execution_score,
        "execution_reasons": best.execution_reasons or [],
        "market_alternatives": alternatives,
    }

    return payload