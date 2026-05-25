# backend/app/odds/execution_market_mapping.py

from __future__ import annotations

from dataclasses import dataclass
from math import fabs
from typing import Any


LOCAL_BOOKMAKERS = {
    "betika",
    "sportpesa",
    "odibets",
    "mozzart",
    "mozzartbet",
}


BOOKMAKER_ALIASES = {
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
class ExecutionCandidate:
    executable_market: str
    executable_selection: str
    bookmaker: str | None
    odds: float | None
    raw_market: str | None
    raw_selection: str | None
    match_quality: str
    execution_family: str
    source_prediction_market: str
    source_prediction_label: str | None
    line_distance: float
    local_bookmaker: bool
    local_realism_score: float
    survivability_score: float
    execution_score: float
    reasons: list[str]


def normalize_bookmaker(value: str | None) -> str | None:
    if not value:
        return None

    key = value.lower().strip()
    return BOOKMAKER_ALIASES.get(key, value.strip())


def is_local_bookmaker(value: str | None) -> bool:
    if not value:
        return False

    normalized = normalize_bookmaker(value)
    if not normalized:
        return False

    return normalized.lower() in LOCAL_BOOKMAKERS


def market_execution_family(market: str) -> str:
    key = market.lower().strip()

    if key.startswith("asian_handicap_"):
        return "asian_handicap_directional"

    if key.startswith("handicap_result_"):
        return "handicap_result_3way"

    if key.startswith("result_total_"):
        return "result_total_goals"

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

    return "other"


def asian_handicap_side(market: str) -> str | None:
    if "_home_" in market:
        return "home"
    if "_away_" in market:
        return "away"
    return None


def asian_handicap_line(market: str) -> float | None:
    key = market.lower()

    if "minus_" in key:
        raw = key.split("minus_", 1)[1]
        return -float(raw.replace("_", "."))

    if "plus_" in key:
        raw = key.split("plus_", 1)[1]
        return float(raw.replace("_", "."))

    if key.endswith("_0_0") or key.endswith("_zero"):
        return 0.0

    return None


def build_asian_handicap_family_candidates(
    *,
    source_market: str,
) -> list[str]:
    side = asian_handicap_side(source_market)
    source_line = asian_handicap_line(source_market)

    if side is None or source_line is None:
        return [source_market]

    preferred_local_lines = [
        -0.25,
        -0.5,
        -0.75,
        -1.0,
        -1.25,
        -1.5,
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
        1.25,
        1.5,
    ]

    ranked = sorted(
        preferred_local_lines,
        key=lambda line: (
            fabs(line - source_line),
            fabs(line),
        ),
    )

    keys: list[str] = []

    for line in ranked:
        if line < 0:
            line_key = f"minus_{str(abs(line)).replace('.', '_')}"
        elif line > 0:
            line_key = f"plus_{str(line).replace('.', '_')}"
        else:
            line_key = "0_0"

        keys.append(f"asian_handicap_{side}_{line_key}")

    return keys


def score_execution_candidate(
    *,
    source_market: str,
    executable_market: str,
    bookmaker: str | None,
    odds: float | None,
    match_quality: str,
    survivability_score: float = 0.50,
) -> tuple[float, list[str]]:
    reasons: list[str] = []

    score = 0.0

    if match_quality == "exact_executable_market":
        score += 100.0
        reasons.append("exact executable market")

    elif match_quality in {"execution_family_fallback", "asian_handicap_family_fallback"}:
        score += 72.0
        reasons.append("family executable fallback")

    elif match_quality in {"exact_canonical", "exact_market_fallback"}:
        score += 55.0
        reasons.append("canonical fallback")

    else:
        score += 20.0
        reasons.append("weak odds match")

    if is_local_bookmaker(bookmaker):
        score += 22.0
        reasons.append("local Kenyan bookmaker")

    if odds is not None:
        if 1.30 <= float(odds) <= 2.40:
            score += 18.0
            reasons.append("local realistic odds band")
        elif 2.40 < float(odds) <= 3.20:
            score += 7.0
            reasons.append("usable but higher odds")
        elif float(odds) > 3.20:
            score -= 20.0
            reasons.append("high odds execution risk")
        else:
            score -= 18.0
            reasons.append("too compressed odds")

    source_line = asian_handicap_line(source_market)
    exec_line = asian_handicap_line(executable_market)

    if source_line is not None and exec_line is not None:
        distance = fabs(source_line - exec_line)

        if distance == 0:
            score += 20.0
            reasons.append("same handicap line")
        elif distance <= 0.25:
            score += 14.0
            reasons.append("nearby handicap line")
        elif distance <= 0.75:
            score += 6.0
            reasons.append("acceptable handicap substitute")
        else:
            score -= 18.0
            reasons.append("far handicap substitute")

    score += max(0.0, min(float(survivability_score), 1.0)) * 20.0

    return round(score, 4), reasons