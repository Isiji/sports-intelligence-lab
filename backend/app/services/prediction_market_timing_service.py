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
    reason: str


def _parse_kickoff(value: Any) -> datetime | None:

    if value is None:
        return None

    if isinstance(value, datetime):
        kickoff = value

    elif isinstance(value, date):
        kickoff = datetime(
            value.year,
            value.month,
            value.day,
        )

    elif isinstance(value, str):
        text = value.strip()

        if not text:
            return None

        try:
            kickoff = datetime.fromisoformat(
                text.replace("Z", "+00:00")
            )

        except ValueError:
            return None

    else:
        return None

    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(
            tzinfo=UTC
        )

    return kickoff.astimezone(EAT)


def analyze_prediction_timing(
    *,
    kickoff_value: Any,
    now: datetime | None = None,
) -> PredictionTimingDecision:

    kickoff_eat_dt = _parse_kickoff(
        kickoff_value
    )

    if kickoff_eat_dt is None:
        return PredictionTimingDecision(
            kickoff_eat=None,
            minutes_to_kickoff=None,
            timing_status="UNKNOWN",
            recommended_action="REVIEW_MANUALLY",
            reason=(
                "Kickoff time is missing or invalid."
            ),
        )

    current_time = now or datetime.now(EAT)

    if current_time.tzinfo is None:
        current_time = current_time.replace(
            tzinfo=EAT
        )

    minutes = int(
        (
            kickoff_eat_dt
            - current_time.astimezone(EAT)
        ).total_seconds()
        // 60
    )

    if minutes < 0:
        status = "LIVE_OR_FINISHED"
        action = "AVOID"
        reason = (
            "Match has already started or finished."
        )

    elif minutes <= 8:
        status = "TOO_CLOSE_TO_KICKOFF"
        action = "AVOID"
        reason = (
            "Too close to kickoff; odds are unstable."
        )

    elif minutes <= 20:
        status = "FINAL_EXECUTION_WINDOW"
        action = "BET_NOW_IF_ODDS_VERIFIED"        
        reason = (
            "Final execution window; only use freshly checked odds."
        )

    elif minutes <= 30:
        status = "LATE_MOVEMENT_WINDOW"
        action = "BET_ONLY_IF_ODDS_STILL_MATCH"
        reason = (
            "Late market movement window; recheck odds before betting."
        )

    elif minutes <= 240:
        status = "PRE_MATCH_OPTIMAL"
        action = "BET_NOW_IF_GROUP_APPROVED"
        reason = (
            "Good pre-match execution window."
        )

    elif minutes <= 1440:
        status = "EARLY_PRE_MATCH"
        action = "WAIT_OR_MONITOR_DRIFT"
        reason = (
            "Match is still far away; monitor odds movement."
        )

    else:
        status = "TOO_EARLY"
        action = "WAIT"
        reason = (
            "Too early for final execution."
        )

    return PredictionTimingDecision(
        kickoff_eat=kickoff_eat_dt.strftime(
            "%Y-%m-%d %H:%M EAT"
        ),
        minutes_to_kickoff=minutes,
        timing_status=status,
        recommended_action=action,
        reason=reason,
    )