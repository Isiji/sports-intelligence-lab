# backend/app/ingest/finished_match_updater.py

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Match, Prediction
from app.ingest.api_football_client import ApiFootballClient


FINISHED_STATUS_CODES = {"FT", "AET", "PEN"}
POSTPONED_STATUS_CODES = {"PST", "TBD"}
CANCELLED_STATUS_CODES = {"CANC", "ABD", "AWD", "WO"}

LIVE_STATUS_CODES = {
    "1H",
    "2H",
    "HT",
    "ET",
    "BT",
    "LIVE",
    "INT",
}


def update_finished_matches(
    session: Session,
    limit: int = 500,
    batch_size: int = 20,
) -> dict:
    """
    Update finished/postponed/cancelled matches from API-Football.

    Production priority:
    1. overdue matches that have predictions
    2. overdue matches without predictions
    3. older unfinished matches as fallback

    This prevents prediction settlement from being blocked by unrelated
    stale rows in the matches table.
    """

    matches = _select_matches_to_update(
        session=session,
        limit=limit,
    )

    client = ApiFootballClient(session=session)

    checked = 0
    updated = 0
    finished = 0
    postponed = 0
    cancelled = 0
    failed = 0
    api_batches = 0
    failures: list[dict] = []

    for batch in _chunked(matches, batch_size):
        fixture_ids = [
            str(match.provider_fixture_id)
            for match in batch
            if match.provider_fixture_id
        ]

        if not fixture_ids:
            continue

        try:
            payload = client.get_fixtures_by_ids(fixture_ids)
            api_batches += 1

            rows = payload.get("response", [])

            if not isinstance(rows, list):
                raise ValueError("Invalid fixture response.")

            rows_by_fixture_id = _index_fixture_rows(rows)

            for match in batch:
                checked += 1

                try:
                    fixture_row = rows_by_fixture_id.get(
                        str(match.provider_fixture_id)
                    )

                    result = _apply_fixture_row_to_match(
                        match=match,
                        fixture_row=fixture_row,
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

        except Exception as exc:
            failed += len(batch)
            session.rollback()

            for match in batch:
                failures.append(
                    {
                        "match_id": match.id,
                        "provider_fixture_id": match.provider_fixture_id,
                        "error": f"batch failed: {exc}",
                    }
                )

            if "Daily API safety limit reached" in str(exc):
                break

    return {
        "matches_selected": len(matches),
        "matches_checked": checked,
        "matches_updated": updated,
        "matches_finished": finished,
        "matches_postponed": postponed,
        "matches_cancelled": cancelled,
        "matches_failed": failed,
        "api_batches_used": api_batches,
        "batch_size": batch_size,
        "failures": failures[:20],
        "updated_at": datetime.utcnow().isoformat(),
    }


def _select_matches_to_update(
    session: Session,
    limit: int,
) -> list[Match]:
    now = datetime.utcnow()

    overdue_predicted_matches = list(
        session.scalars(
            select(Match)
            .join(
                Prediction,
                Prediction.match_id == Match.id,
            )
            .where(
                Match.provider == "api-football",
                Match.provider_fixture_id.isnot(None),
                Match.is_finished.is_(False),
                Match.is_postponed.is_(False),
                Match.is_cancelled.is_(False),
                Match.kickoff_datetime.isnot(None),
                Match.kickoff_datetime < now,
            )
            .distinct()
            .order_by(Match.kickoff_datetime.asc())
            .limit(limit)
        )
    )

    if len(overdue_predicted_matches) >= limit:
        return overdue_predicted_matches[:limit]

    selected_by_id = {
        match.id: match
        for match in overdue_predicted_matches
    }

    remaining = limit - len(selected_by_id)

    overdue_unpredicted_matches = list(
        session.scalars(
            select(Match)
            .where(
                Match.provider == "api-football",
                Match.provider_fixture_id.isnot(None),
                Match.is_finished.is_(False),
                Match.is_postponed.is_(False),
                Match.is_cancelled.is_(False),
                Match.kickoff_datetime.isnot(None),
                Match.kickoff_datetime < now,
                Match.id.notin_(selected_by_id.keys())
                if selected_by_id
                else True,
            )
            .order_by(Match.kickoff_datetime.asc())
            .limit(remaining)
        )
    )

    for match in overdue_unpredicted_matches:
        selected_by_id[match.id] = match

    if len(selected_by_id) >= limit:
        return list(selected_by_id.values())[:limit]

    remaining = limit - len(selected_by_id)

    fallback_matches = list(
        session.scalars(
            select(Match)
            .where(
                Match.provider == "api-football",
                Match.provider_fixture_id.isnot(None),
                Match.is_finished.is_(False),
                Match.is_cancelled.is_(False),
                Match.id.notin_(selected_by_id.keys())
                if selected_by_id
                else True,
            )
            .order_by(
                Match.kickoff_date.asc(),
                Match.id.asc(),
            )
            .limit(remaining)
        )
    )

    for match in fallback_matches:
        selected_by_id[match.id] = match

    return list(selected_by_id.values())[:limit]


def _index_fixture_rows(
    rows: list[dict],
) -> dict[str, dict]:
    rows_by_fixture_id: dict[str, dict] = {}

    for row in rows:
        fixture = row.get("fixture") or {}
        provider_fixture_id = fixture.get("id")

        if provider_fixture_id is not None:
            rows_by_fixture_id[str(provider_fixture_id)] = row

    return rows_by_fixture_id


def _apply_fixture_row_to_match(
    match: Match,
    fixture_row: dict | None,
) -> dict:
    if not fixture_row:
        return {
            "updated": False,
            "is_finished": bool(match.is_finished),
            "is_postponed": bool(match.is_postponed),
            "is_cancelled": bool(match.is_cancelled),
        }

    fixture = fixture_row.get("fixture") or {}
    goals = fixture_row.get("goals") or {}
    league = fixture_row.get("league") or {}
    teams = fixture_row.get("teams") or {}

    status = fixture.get("status") or {}
    status_short = str(
        status.get("short")
        or match.status
        or "unknown"
    ).upper()

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
        _mark_finished(
            match=match,
            home_goals=home_goals,
            away_goals=away_goals,
            force_status=status_short,
        )

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
        has_real_scores = (
            home_goals is not None
            and away_goals is not None
        )

        is_live_state = status_short in LIVE_STATUS_CODES

        if has_real_scores and not is_live_state:
            _mark_finished(
                match=match,
                home_goals=home_goals,
                away_goals=away_goals,
                force_status="FT",
            )
        else:
            match.is_finished = False
            match.is_valid_for_training = False

    new_state = _snapshot_match(match)

    return {
        "updated": old_state != new_state,
        "is_finished": bool(match.is_finished),
        "is_postponed": bool(match.is_postponed),
        "is_cancelled": bool(match.is_cancelled),
    }


def _mark_finished(
    match: Match,
    home_goals: int | None,
    away_goals: int | None,
    force_status: str,
) -> None:
    match.is_finished = True
    match.is_postponed = False
    match.is_cancelled = False
    match.status = force_status

    if home_goals is not None:
        match.home_goals = int(home_goals)

    if away_goals is not None:
        match.away_goals = int(away_goals)

    match.is_valid_for_training = (
        match.home_goals is not None
        and match.away_goals is not None
    )


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


def _chunked(
    items: list,
    size: int,
) -> list[list]:
    if size <= 0:
        size = 20

    return [
        items[index:index + size]
        for index in range(0, len(items), size)
    ]