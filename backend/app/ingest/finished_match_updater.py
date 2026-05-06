# backend/app/ingest/finished_match_updater.py

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Match
from app.ingest.api_football_client import ApiFootballClient


FINISHED_STATUS_CODES = {"FT", "AET", "PEN"}
POSTPONED_STATUS_CODES = {"PST", "TBD"}
CANCELLED_STATUS_CODES = {"CANC", "ABD", "AWD", "WO"}


def update_finished_matches(
    session: Session,
    limit: int = 500,
) -> dict:
    matches = list(
        session.scalars(
            select(Match)
            .where(
                Match.provider == "api-football",
                Match.provider_fixture_id.isnot(None),
                Match.is_finished.is_(False),
                Match.is_cancelled.is_(False),
            )
            .order_by(Match.kickoff_date.asc())
            .limit(limit)
        )
    )

    client = ApiFootballClient(session=session)

    checked = 0
    updated = 0
    finished = 0
    postponed = 0
    cancelled = 0
    failed = 0
    failures = []

    for match in matches:
        checked += 1

        try:
            result = _update_single_match_from_provider(
                session=session,
                client=client,
                match=match,
            )

            if result["updated"]:
                updated += 1

            if result["is_finished"]:
                finished += 1

            if result["is_postponed"]:
                postponed += 1

            if result["is_cancelled"]:
                cancelled += 1

        except Exception as exc:
            failed += 1
            session.rollback()

            failures.append(
                {
                    "match_id": match.id,
                    "provider_fixture_id": match.provider_fixture_id,
                    "error": str(exc),
                }
            )

    session.commit()

    return {
        "matches_checked": checked,
        "matches_updated": updated,
        "matches_finished": finished,
        "matches_postponed": postponed,
        "matches_cancelled": cancelled,
        "matches_failed": failed,
        "failures": failures[:20],
        "updated_at": datetime.utcnow().isoformat(),
    }


def _update_single_match_from_provider(
    session: Session,
    client: ApiFootballClient,
    match: Match,
) -> dict:
    payload = client.get(
        endpoint="fixtures",
        params={
            "id": match.provider_fixture_id,
        },
    )

    rows = payload.get("response", [])

    if not isinstance(rows, list):
        raise ValueError("Invalid fixture response.")

    if not rows:
        return {
            "updated": False,
            "is_finished": bool(match.is_finished),
            "is_postponed": bool(match.is_postponed),
            "is_cancelled": bool(match.is_cancelled),
        }

    fixture_row = rows[0]

    fixture = fixture_row.get("fixture") or {}
    goals = fixture_row.get("goals") or {}
    league = fixture_row.get("league") or {}
    teams = fixture_row.get("teams") or {}

    status = fixture.get("status") or {}
    status_short = status.get("short") or match.status or "unknown"

    home_goals = goals.get("home")
    away_goals = goals.get("away")

    old_state = _snapshot_match(match)

    match.status = status_short
    match.last_synced_at = datetime.utcnow()

    if league.get("round"):
        match.round_name = league.get("round")

    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}

    if home_team.get("name"):
        match.home_team = home_team["name"]

    if away_team.get("name"):
        match.away_team = away_team["name"]

    if status_short in FINISHED_STATUS_CODES:
        match.is_finished = True
        match.is_postponed = False
        match.is_cancelled = False
        match.is_valid_for_training = True

        if home_goals is not None:
            match.home_goals = int(home_goals)

        if away_goals is not None:
            match.away_goals = int(away_goals)

    elif status_short in POSTPONED_STATUS_CODES:
        match.is_finished = False
        match.is_postponed = True
        match.is_cancelled = False
        match.is_valid_for_training = False

    elif status_short in CANCELLED_STATUS_CODES:
        match.is_finished = False
        match.is_postponed = False
        match.is_cancelled = True
        match.is_valid_for_training = False

    else:
        match.is_finished = False
        match.is_valid_for_training = False

    session.add(match)

    new_state = _snapshot_match(match)

    return {
        "updated": old_state != new_state,
        "is_finished": bool(match.is_finished),
        "is_postponed": bool(match.is_postponed),
        "is_cancelled": bool(match.is_cancelled),
    }


def _snapshot_match(match: Match) -> dict:
    return {
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "status": match.status,
        "round_name": match.round_name,
        "is_finished": bool(match.is_finished),
        "is_postponed": bool(match.is_postponed),
        "is_cancelled": bool(match.is_cancelled),
        "is_valid_for_training": bool(match.is_valid_for_training),
    }