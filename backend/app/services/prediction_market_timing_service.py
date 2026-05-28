# backend/app/services/prediction_market_timing_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


EAT = ZoneInfo("Africa/Nairobi")
UTC = timezone.utc


@dataclass(frozen=True)
class PredictionTimingDecision:
    kickoff_eat: str | None
    minutes_to_kickoff: int | None
    timing_status: str
    recommended_action: str
    timing_score: float
    execution_allowed: bool
    grouping_allowed: bool
    reason: str


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value

    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)

    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(EAT)


def _minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def analyze_prediction_timing(
    *,
    kickoff_value: Any,
    odds_retrieved_at: Any | None = None,
    execution_ready: bool | None = None,
    stale_odds: bool | None = None,
    now: datetime | None = None,
) -> PredictionTimingDecision:
    kickoff_eat_dt = _parse_datetime(kickoff_value)

    if kickoff_eat_dt is None:
        return PredictionTimingDecision(
            kickoff_eat=None,
            minutes_to_kickoff=None,
            timing_status="UNKNOWN",
            recommended_action="REVIEW_MANUALLY",
            timing_score=0.0,
            execution_allowed=False,
            grouping_allowed=False,
            reason="Kickoff time is missing or invalid.",
        )

    current_time = now or datetime.now(EAT)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=EAT)

    current_time = current_time.astimezone(EAT)

    minutes_to_kickoff = _minutes_between(
        current_time,
        kickoff_eat_dt,
    )

    odds_dt = _parse_datetime(odds_retrieved_at)
    odds_age_minutes: int | None = None

    if odds_dt is not None:
        odds_age_minutes = max(
            0,
            _minutes_between(
                odds_dt,
                current_time,
            ),
        )

    if execution_ready is False:
        return PredictionTimingDecision(
            kickoff_eat=kickoff_eat_dt.strftime("%Y-%m-%d %H:%M EAT"),
            minutes_to_kickoff=minutes_to_kickoff,
            timing_status="EXECUTION_NOT_READY",
            recommended_action="AVOID",
            timing_score=0.0,
            execution_allowed=False,
            grouping_allowed=False,
            reason="Prediction is not execution-ready.",
        )

    if stale_odds is True:
        return PredictionTimingDecision(
            kickoff_eat=kickoff_eat_dt.strftime("%Y-%m-%d %H:%M EAT"),
            minutes_to_kickoff=minutes_to_kickoff,
            timing_status="STALE_ODDS",
            recommended_action="RECHECK_ODDS_BEFORE_BETTING",
            timing_score=0.25,
            execution_allowed=False,
            grouping_allowed=False,
            reason="Stored odds are stale and must be refreshed.",
        )

    if minutes_to_kickoff < 0:
        status = "LIVE_OR_FINISHED"
        action = "AVOID"
        score = 0.0
        allowed = False
        reason = "Match has already started or finished."

    elif minutes_to_kickoff <= 8:
        status = "TOO_CLOSE_TO_KICKOFF"
        action = "AVOID"
        score = 0.1
        allowed = False
        reason = "Too close to kickoff; execution risk is too high."

    elif minutes_to_kickoff <= 20:
        status = "FINAL_EXECUTION_WINDOW"
        action = "BET_NOW_IF_ODDS_VERIFIED"
        score = 0.75
        allowed = True
        reason = "Final execution window; only use freshly checked odds."

    elif minutes_to_kickoff <= 30:
        status = "LATE_MOVEMENT_WINDOW"
        action = "BET_ONLY_IF_ODDS_STILL_MATCH"
        score = 0.7
        allowed = True
        reason = "Late market movement window; recheck odds before betting."

    elif minutes_to_kickoff <= 240:
        status = "PRE_MATCH_OPTIMAL"
        action = "BET_NOW_IF_GROUP_APPROVED"
        score = 1.0
        allowed = True
        reason = "Good pre-match execution window."

    elif minutes_to_kickoff <= 1440:
        status = "EARLY_PRE_MATCH"
        action = "PLACE_EARLY_ONLY_IF_VALUE_AND_GROUP_ARE_STRONG"
        score = 0.65
        allowed = True
        reason = "Tomorrow-game window; acceptable, but monitor odds drift."

    else:
        status = "TOO_EARLY"
        action = "WAIT"
        score = 0.35
        allowed = False
        reason = "Too early for final execution."

    if odds_age_minutes is not None:
        if odds_age_minutes > 360:
            score *= 0.55
            reason += " Odds are old and should be refreshed."
        elif odds_age_minutes > 120:
            score *= 0.75
            reason += " Odds are moderately old; recheck before execution."

    return PredictionTimingDecision(
        kickoff_eat=kickoff_eat_dt.strftime("%Y-%m-%d %H:%M EAT"),
        minutes_to_kickoff=minutes_to_kickoff,
        timing_status=status,
        recommended_action=action,
        timing_score=round(score, 4),
        execution_allowed=allowed,
        grouping_allowed=allowed and score >= 0.55,
        reason=reason,
    )