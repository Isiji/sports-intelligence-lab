from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Match, TeamMatchStat
from app.ingest.api_football_client import ApiFootballClient


STAT_NAME_MAP = {
    "Shots on Goal": "shots_on_target",
    "Corner Kicks": "corners",
    "Ball Possession": "possession",
    "Fouls": "fouls",
    "Yellow Cards": "cards",
    "Goalkeeper Saves": "keeper_saves",
}


def ingest_fixture_statistics(
    session: Session,
    match_id: int,
) -> dict:
    match = session.get(Match, match_id)

    if match is None:
        raise ValueError("Match not found.")

    if not match.provider_fixture_id:
        raise ValueError("Match has no provider fixture ID.")

    client = ApiFootballClient(session=session)

    payload = client.get(
        endpoint="fixtures/statistics",
        params={
            "fixture": match.provider_fixture_id,
        },
    )

    rows = payload.get("response", [])

    if not isinstance(rows, list):
        raise ValueError("Invalid statistics response.")

    updated_teams = 0

    for team_block in rows:
        team_info = team_block.get("team") or {}
        statistics = team_block.get("statistics") or []

        team_name = team_info.get("name")

        if not team_name:
            continue

        stat_row = session.scalar(
            select(TeamMatchStat).where(
                TeamMatchStat.match_id == match.id,
                TeamMatchStat.team == team_name,
            )
        )

        if stat_row is None:
            continue

        parsed = _parse_statistics(statistics)

        stat_row.shots_on_target = parsed["shots_on_target"]
        stat_row.corners = parsed["corners"]
        stat_row.possession = parsed["possession"]
        stat_row.fouls = parsed["fouls"]
        stat_row.cards = parsed["cards"]
        stat_row.keeper_saves = parsed["keeper_saves"]

        updated_teams += 1

    session.commit()

    return {
        "match_id": match.id,
        "provider_fixture_id": match.provider_fixture_id,
        "teams_updated": updated_teams,
        "updated_at": datetime.utcnow().isoformat(),
    }


def ingest_missing_statistics(
    session: Session,
    limit: int = 100,
) -> dict:
    matches = list(
        session.scalars(
            select(Match)
            .where(
                Match.provider == "api-football",
                Match.home_goals.isnot(None),
                Match.away_goals.isnot(None),
            )
            .order_by(Match.kickoff_date.desc())
            .limit(limit)
        )
    )

    processed = 0
    failed = 0

    failures = []

    for match in matches:
        try:
            result = ingest_fixture_statistics(
                session=session,
                match_id=match.id,
            )

            if result["teams_updated"] > 0:
                processed += 1

        except Exception as exc:
            failed += 1

            failures.append(
                {
                    "match_id": match.id,
                    "error": str(exc),
                }
            )

    return {
        "matches_processed": processed,
        "matches_failed": failed,
        "failures": failures[:20],
    }


def _parse_statistics(stat_rows: list[dict]) -> dict:
    parsed = {
        "shots_on_target": 0,
        "corners": 0,
        "possession": 0.0,
        "fouls": 0,
        "cards": 0,
        "keeper_saves": 0,
    }

    yellow_cards = 0
    red_cards = 0

    for row in stat_rows:
        stat_type = row.get("type")
        raw_value = row.get("value")

        if stat_type == "Yellow Cards":
            yellow_cards = _safe_int(raw_value)
            continue

        if stat_type == "Red Cards":
            red_cards = _safe_int(raw_value)
            continue

        field_name = STAT_NAME_MAP.get(stat_type)

        if not field_name:
            continue

        if field_name == "possession":
            parsed[field_name] = _safe_percentage(raw_value)
        else:
            parsed[field_name] = _safe_int(raw_value)

    parsed["cards"] = yellow_cards + red_cards

    return parsed


def _safe_int(value) -> int:
    if value is None:
        return 0

    try:
        if isinstance(value, str):
            value = value.replace("%", "").strip()

        return int(float(value))

    except (TypeError, ValueError):
        return 0


def _safe_percentage(value) -> float:
    if value is None:
        return 0.0

    try:
        if isinstance(value, str):
            value = value.replace("%", "").strip()

        return round(float(value), 2)

    except (TypeError, ValueError):
        return 0.0