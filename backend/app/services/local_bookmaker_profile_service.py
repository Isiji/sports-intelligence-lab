# backend/app/services/local_bookmaker_profile_service.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.odds.executable_market_registry import parse_executable_market


KENYAN_BOOKMAKERS = {
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
class LocalBookmakerProfile:
    bookmaker: str
    availability_bias: float
    odds_compression: float
    handicap_depth: float
    derivative_depth: float
    timing_stability: float


BOOKMAKER_PROFILES = {
    "Betika": LocalBookmakerProfile("Betika", 0.88, 0.78, 0.55, 0.42, 0.74),
    "SportPesa": LocalBookmakerProfile("SportPesa", 0.84, 0.76, 0.50, 0.38, 0.70),
    "Odibets": LocalBookmakerProfile("Odibets", 0.80, 0.74, 0.46, 0.35, 0.68),
    "Mozzart": LocalBookmakerProfile("Mozzart", 0.86, 0.80, 0.60, 0.48, 0.76),
}


@dataclass
class KenyaExecutionProfile:
    market: str
    bookmaker: str | None
    kenya_available: bool
    kenya_grade: str
    market_availability_score: float
    line_realism_score: float
    odds_compression_factor: float
    local_value_score: float | None
    local_execution_score: float
    preferred_fallbacks: list[str]
    warnings: list[str]
    reasons: list[str]


def evaluate_kenyan_execution(
    *,
    market: str,
    bookmaker: str | None = None,
    odds: float | None = None,
    confidence: float | None = None,
    source_market: str | None = None,
) -> dict[str, Any]:

    normalized_bookmaker = normalize_kenyan_bookmaker(bookmaker)
    parsed = parse_executable_market(market)

    profile = (
        BOOKMAKER_PROFILES.get(normalized_bookmaker)
        if normalized_bookmaker
        else None
    )

    availability = _market_availability_score(
        family=parsed.family,
        profile=profile,
    )

    line_realism = _line_realism_score(
        family=parsed.family,
        line=parsed.line,
        source_market=source_market,
    )

    compression = _odds_compression_factor(
        odds=odds,
        family=parsed.family,
        profile=profile,
    )

    local_value_score = _local_value_score(
        odds=odds,
        confidence=confidence,
    )

    warnings: list[str] = []
    reasons: list[str] = []

    if normalized_bookmaker:
        reasons.append(f"Kenyan bookmaker profile matched: {normalized_bookmaker}")
    else:
        warnings.append("No Kenyan bookmaker matched; using generic Kenya realism profile")

    if availability < 0.45:
        warnings.append("Market has weak Kenyan bookmaker availability")

    if line_realism < 0.45:
        warnings.append("Line is weak/unrealistic for Kenyan bookmaker execution")

    if odds is not None and odds < 1.25:
        warnings.append("Odds are heavily compressed")

    if local_value_score is not None and local_value_score < 0:
        warnings.append("Kenyan odds are value-negative")

    if (
        parsed.family == "ASIAN_HANDICAP"
        and parsed.line is not None
        and parsed.line > 0
        and source_market
        and "minus" in source_market.lower()
    ):
        warnings.append("Do not replace protected positive AH with negative AH")
        line_realism = min(line_realism, 0.25)

    local_execution_score = _local_execution_score(
        availability=availability,
        line_realism=line_realism,
        compression=compression,
        local_value_score=local_value_score,
        profile=profile,
    )

    kenya_grade = _kenya_grade(local_execution_score)

    kenya_available = (
        availability >= 0.50
        and line_realism >= 0.45
        and local_execution_score >= 50.0
    )

    return asdict(
        KenyaExecutionProfile(
            market=market,
            bookmaker=normalized_bookmaker,
            kenya_available=kenya_available,
            kenya_grade=kenya_grade,
            market_availability_score=round(availability, 4),
            line_realism_score=round(line_realism, 4),
            odds_compression_factor=round(compression, 4),
            local_value_score=(
                round(local_value_score, 6)
                if local_value_score is not None
                else None
            ),
            local_execution_score=round(local_execution_score, 4),
            preferred_fallbacks=preferred_kenyan_fallbacks(market),
            warnings=warnings,
            reasons=reasons,
        )
    )


def normalize_kenyan_bookmaker(bookmaker: str | None) -> str | None:
    if not bookmaker:
        return None

    key = bookmaker.lower().strip()

    return KENYAN_BOOKMAKERS.get(key)


def is_kenyan_bookmaker(bookmaker: str | None) -> bool:
    return normalize_kenyan_bookmaker(bookmaker) is not None


def preferred_kenyan_fallbacks(market: str) -> list[str]:
    parsed = parse_executable_market(market)

    if parsed.family == "ASIAN_HANDICAP":

        if parsed.side == "HOME":
            if parsed.line is not None and parsed.line > 0:
                return [
                    "double_chance_1x",
                    "draw_no_bet_home",
                    "home_win",
                    "over_1_5_goals",
                ]

            if parsed.line == 0:
                return [
                    "draw_no_bet_home",
                    "home_win",
                    "double_chance_1x",
                ]

            return [
                market,
                "home_win",
                "draw_no_bet_home",
            ]

        if parsed.side == "AWAY":
            if parsed.line is not None and parsed.line > 0:
                return [
                    "double_chance_x2",
                    "draw_no_bet_away",
                    "away_win",
                    "over_1_5_goals",
                ]

            if parsed.line == 0:
                return [
                    "draw_no_bet_away",
                    "away_win",
                    "double_chance_x2",
                ]

            return [
                market,
                "away_win",
                "draw_no_bet_away",
            ]

    if market == "home_win":
        return [
            "home_win",
            "draw_no_bet_home",
            "double_chance_1x",
        ]

    if market == "away_win":
        return [
            "away_win",
            "draw_no_bet_away",
            "double_chance_x2",
        ]

    if market == "draw":
        return [
            "draw",
            "double_chance_12",
            "under_3_5_goals",
        ]

    if market == "double_chance_1x":
        return [
            "double_chance_1x",
            "draw_no_bet_home",
            "home_win",
        ]

    if market == "double_chance_x2":
        return [
            "double_chance_x2",
            "draw_no_bet_away",
            "away_win",
        ]

    if parsed.family in {"GOALS_TOTAL", "BTTS"}:
        return [
            market,
            "over_1_5_goals",
            "under_3_5_goals",
            "btts_yes",
            "btts_no",
        ]

    return [market]


def _market_availability_score(
    *,
    family: str,
    profile: LocalBookmakerProfile | None,
) -> float:

    base = {
        "MATCH_RESULT": 0.98,
        "DOUBLE_CHANCE": 0.94,
        "GOALS_TOTAL": 0.92,
        "BTTS": 0.86,
        "DRAW_NO_BET": 0.78,
        "ASIAN_HANDICAP": 0.58,
        "TEAM_TOTAL": 0.55,
        "FIRST_HALF_GOALS_TOTAL": 0.52,
        "FIRST_HALF_RESULT": 0.50,
        "HANDICAP_RESULT": 0.36,
        "RESULT_TOTAL": 0.30,
        "CORNERS": 0.34,
        "SHOTS_ON_TARGET": 0.24,
        "FIRST_HALF_DOUBLE_CHANCE": 0.28,
    }.get(family, 0.25)

    if profile:
        base = (base * 0.75) + (profile.availability_bias * 0.25)

        if family == "ASIAN_HANDICAP":
            base = (base * 0.65) + (profile.handicap_depth * 0.35)

        if family in {
            "RESULT_TOTAL",
            "HANDICAP_RESULT",
            "FIRST_HALF_DOUBLE_CHANCE",
        }:
            base = (base * 0.70) + (profile.derivative_depth * 0.30)

    return max(0.0, min(base, 1.0))


def _line_realism_score(
    *,
    family: str,
    line: float | None,
    source_market: str | None,
) -> float:

    if family != "ASIAN_HANDICAP":
        return 0.90

    if line is None:
        return 0.35

    if line in {-0.5, 0.0, 0.5, 1.0, -1.0}:
        score = 0.74
    elif line in {0.25, 0.75, -0.25, -0.75}:
        score = 0.58
    elif abs(line) >= 1.5:
        score = 0.42
    else:
        score = 0.50

    if line > 0:
        score += 0.05

    if source_market:
        source = source_market.lower()

        if line > 0 and "minus" in source:
            score -= 0.45

        if line < 0 and "plus" in source:
            score -= 0.35

    return max(0.0, min(score, 1.0))


def _odds_compression_factor(
    *,
    odds: float | None,
    family: str,
    profile: LocalBookmakerProfile | None,
) -> float:

    base = profile.odds_compression if profile else 0.76

    if odds is None:
        return base

    if odds < 1.20:
        base -= 0.30
    elif odds < 1.35:
        base -= 0.18
    elif 1.35 <= odds <= 2.10:
        base += 0.08
    elif 2.10 < odds <= 3.00:
        base += 0.02
    elif odds > 4.00:
        base -= 0.20

    if family in {"DOUBLE_CHANCE", "GOALS_TOTAL"} and odds < 1.35:
        base -= 0.08

    return max(0.0, min(base, 1.0))


def _local_value_score(
    *,
    odds: float | None,
    confidence: float | None,
) -> float | None:

    if odds is None or confidence is None or odds <= 0:
        return None

    return float(confidence) - (1.0 / float(odds))


def _local_execution_score(
    *,
    availability: float,
    line_realism: float,
    compression: float,
    local_value_score: float | None,
    profile: LocalBookmakerProfile | None,
) -> float:

    score = 0.0

    score += availability * 35.0
    score += line_realism * 28.0
    score += compression * 22.0

    if profile:
        score += profile.timing_stability * 8.0
    else:
        score += 4.0

    if local_value_score is not None:
        if local_value_score >= 0.08:
            score += 12.0
        elif local_value_score >= 0.03:
            score += 7.0
        elif local_value_score >= 0.00:
            score += 2.0
        else:
            score -= min(abs(local_value_score) * 80.0, 18.0)

    return max(0.0, min(score, 100.0))


def _kenya_grade(score: float) -> str:
    if score >= 78.0:
        return "KENYA_STRONG"

    if score >= 62.0:
        return "KENYA_ACCEPTABLE"

    if score >= 45.0:
        return "KENYA_WEAK"

    return "KENYA_UNAVAILABLE"