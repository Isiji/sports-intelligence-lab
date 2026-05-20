# backend/app/services/tournament_context_service.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TournamentContext:
    is_international: bool
    is_neutral_venue: bool
    tournament_type: str
    tournament_stage: str
    competition_priority: float
    tournament_pressure_score: float


INTERNATIONAL_KEYWORDS = {
    "world cup",
    "afcon",
    "africa cup",
    "euro",
    "uefa european championship",
    "copa america",
    "nations league",
    "qualification",
    "qualifiers",
    "friendlies",
    "friendly",
    "intercontinental",
    "asian cup",
    "concacaf",
    "caf",
    "ofc",
    "conmebol",
    "uefa",
    "fifa",
}

ELITE_TOURNAMENT_KEYWORDS = {
    "world cup": 1.00,
    "euro": 0.92,
    "uefa european championship": 0.92,
    "copa america": 0.90,
    "afcon": 0.86,
    "africa cup": 0.86,
    "nations league": 0.72,
    "asian cup": 0.74,
    "concacaf": 0.68,
    "qualification": 0.65,
    "qualifiers": 0.65,
    "intercontinental": 0.78,
    "friendlies": 0.35,
    "friendly": 0.35,
}

CLUB_CUP_KEYWORDS = {
    "champions league",
    "europa league",
    "conference league",
    "fa cup",
    "carabao",
    "copa del rey",
    "coppa",
    "dfb pokal",
    "cup",
}

KNOCKOUT_KEYWORDS = {
    "round of 16",
    "8th finals",
    "quarter",
    "semi",
    "final",
    "play-off",
    "playoff",
    "knockout",
}

GROUP_STAGE_KEYWORDS = {
    "group",
    "group stage",
}

QUALIFIER_KEYWORDS = {
    "qualification",
    "qualifier",
    "qualifiers",
}

FRIENDLY_KEYWORDS = {
    "friendly",
    "friendlies",
}


def resolve_tournament_context(
    *,
    league_name: str | None,
    round_name: str | None,
    country_name: str | None = None,
) -> TournamentContext:
    league = _clean(league_name)
    round_value = _clean(round_name)
    country = _clean(country_name)

    combined = " ".join([league, round_value, country]).strip()

    is_international = any(
        keyword in combined
        for keyword in INTERNATIONAL_KEYWORDS
    )

    tournament_type = _resolve_tournament_type(combined)
    tournament_stage = _resolve_tournament_stage(round_value, combined)

    is_neutral_venue = _resolve_neutral_venue(
        tournament_type=tournament_type,
        tournament_stage=tournament_stage,
        combined=combined,
    )

    competition_priority = _resolve_competition_priority(
        combined=combined,
        tournament_type=tournament_type,
        tournament_stage=tournament_stage,
        is_international=is_international,
    )

    pressure_score = _resolve_pressure_score(
        tournament_type=tournament_type,
        tournament_stage=tournament_stage,
        competition_priority=competition_priority,
        is_neutral_venue=is_neutral_venue,
    )

    return TournamentContext(
        is_international=is_international,
        is_neutral_venue=is_neutral_venue,
        tournament_type=tournament_type,
        tournament_stage=tournament_stage,
        competition_priority=round(competition_priority, 4),
        tournament_pressure_score=round(pressure_score, 4),
    )


def _resolve_tournament_type(combined: str) -> str:
    if any(keyword in combined for keyword in FRIENDLY_KEYWORDS):
        return "international_friendly"

    if "world cup" in combined:
        return "world_cup"

    if any(keyword in combined for keyword in QUALIFIER_KEYWORDS):
        return "international_qualifier"

    if any(keyword in combined for keyword in INTERNATIONAL_KEYWORDS):
        return "international_tournament"

    if any(keyword in combined for keyword in CLUB_CUP_KEYWORDS):
        return "club_cup"

    return "league"


def _resolve_tournament_stage(round_value: str, combined: str) -> str:
    text = f"{round_value} {combined}"

    if "final" in text and "semi" not in text and "quarter" not in text:
        return "final"

    if "semi" in text:
        return "semifinal"

    if "quarter" in text:
        return "quarterfinal"

    if "round of 16" in text or "8th finals" in text:
        return "round_of_16"

    if "play-off" in text or "playoff" in text:
        return "playoff"

    if any(keyword in text for keyword in GROUP_STAGE_KEYWORDS):
        return "group_stage"

    if any(keyword in text for keyword in QUALIFIER_KEYWORDS):
        return "qualifier"

    if any(keyword in text for keyword in FRIENDLY_KEYWORDS):
        return "friendly"

    if any(keyword in text for keyword in KNOCKOUT_KEYWORDS):
        return "knockout"

    return "regular"


def _resolve_neutral_venue(
    *,
    tournament_type: str,
    tournament_stage: str,
    combined: str,
) -> bool:
    if tournament_type in {
        "world_cup",
        "international_tournament",
        "international_friendly",
    }:
        return True

    if tournament_stage in {
        "final",
        "semifinal",
        "quarterfinal",
        "round_of_16",
        "playoff",
        "knockout",
    } and tournament_type in {"club_cup", "international_qualifier"}:
        return True

    return False


def _resolve_competition_priority(
    *,
    combined: str,
    tournament_type: str,
    tournament_stage: str,
    is_international: bool,
) -> float:
    priority = 0.30

    for keyword, score in ELITE_TOURNAMENT_KEYWORDS.items():
        if keyword in combined:
            priority = max(priority, score)

    if tournament_type == "league":
        priority = max(priority, 0.40)

    if tournament_type == "club_cup":
        priority = max(priority, 0.55)

    if is_international:
        priority = max(priority, 0.62)

    if tournament_stage in {"final", "semifinal"}:
        priority += 0.10

    elif tournament_stage in {"quarterfinal", "round_of_16", "playoff"}:
        priority += 0.07

    elif tournament_stage == "qualifier":
        priority += 0.05

    return min(priority, 1.0)


def _resolve_pressure_score(
    *,
    tournament_type: str,
    tournament_stage: str,
    competition_priority: float,
    is_neutral_venue: bool,
) -> float:
    score = competition_priority * 0.55

    if tournament_type in {
        "world_cup",
        "international_tournament",
        "international_qualifier",
    }:
        score += 0.15

    if tournament_stage == "final":
        score += 0.25

    elif tournament_stage == "semifinal":
        score += 0.20

    elif tournament_stage in {"quarterfinal", "round_of_16", "playoff", "knockout"}:
        score += 0.15

    elif tournament_stage == "group_stage":
        score += 0.05

    if is_neutral_venue:
        score += 0.05

    if tournament_stage == "friendly":
        score *= 0.45

    return min(score, 1.0)


def _clean(value: str | None) -> str:
    return " ".join(str(value or "").lower().strip().split())