from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Competition,
    Country,
    Match,
    ProviderSyncLog,
    Team,
    TeamMatchStat,
)
from app.ingest.api_football_client import ApiFootballClient


FINISHED_STATUSES = {"FT", "AET", "PEN"}
POSTPONED_STATUSES = {"PST", "POSTPONED"}
CANCELLED_STATUSES = {"CANC", "CANCELLED", "ABD", "SUSP"}


def ingest_fixtures_for_date(
    session: Session,
    date_value: date,
) -> dict[str, int | str]:
    client = ApiFootballClient(session=session)

    sync_log = ProviderSyncLog(
        provider="api-football",
        sync_type="fixtures_by_date",
        status="started",
    )

    session.add(sync_log)
    session.commit()
    session.refresh(sync_log)

    records_received = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0

    try:
        payload = client.get_fixtures_by_date(date_value.isoformat())
        fixtures = payload.get("response", [])

        if not isinstance(fixtures, list):
            raise ValueError("API response field 'response' is not a list.")

        records_received = len(fixtures)

        for item in fixtures:
            result = _upsert_fixture(
                session=session,
                item=item,
            )

            if result == "inserted":
                records_inserted += 1
            elif result == "updated":
                records_updated += 1
            else:
                records_skipped += 1

        sync_log.status = "success"
        sync_log.finished_at = datetime.utcnow()
        sync_log.records_received = records_received
        sync_log.records_inserted = records_inserted
        sync_log.records_updated = records_updated
        sync_log.records_skipped = records_skipped

        session.commit()

        return {
            "status": "success",
            "records_received": records_received,
            "records_inserted": records_inserted,
            "records_updated": records_updated,
            "records_skipped": records_skipped,
        }

    except Exception as exc:
        sync_log.status = "failed"
        sync_log.finished_at = datetime.utcnow()
        sync_log.error_message = str(exc)
        sync_log.records_received = records_received
        sync_log.records_inserted = records_inserted
        sync_log.records_updated = records_updated
        sync_log.records_skipped = records_skipped

        session.commit()
        raise


def _upsert_fixture(
    session: Session,
    item: dict[str, Any],
) -> str:
    fixture_data = item.get("fixture") or {}
    league_data = item.get("league") or {}
    teams_data = item.get("teams") or {}
    goals_data = item.get("goals") or {}

    fixture_id = fixture_data.get("id")

    if fixture_id is None:
        return "skipped"

    provider_fixture_id = str(fixture_id)

    home_data = teams_data.get("home") or {}
    away_data = teams_data.get("away") or {}

    home_name = home_data.get("name")
    away_name = away_data.get("name")

    if not home_name or not away_name:
        return "skipped"

    kickoff_datetime = _parse_datetime(fixture_data.get("date"))

    if kickoff_datetime is None:
        return "skipped"

    country = _get_or_create_country(
        session=session,
        name=league_data.get("country"),
    )

    competition = _get_or_create_competition(
        session=session,
        country_id=country.id if country else None,
        league_data=league_data,
    )

    home_team = _get_or_create_team(
        session=session,
        country_id=country.id if country else None,
        team_data=home_data,
    )

    away_team = _get_or_create_team(
        session=session,
        country_id=country.id if country else None,
        team_data=away_data,
    )

    status_short = (
        fixture_data.get("status", {}).get("short")
        or "scheduled"
    )

    match = session.scalar(
        select(Match).where(
            Match.provider == "api-football",
            Match.provider_fixture_id == provider_fixture_id,
        )
    )

    is_new = match is None

    if match is None:
        match = Match(
            sport="football",
            provider="api-football",
            provider_fixture_id=provider_fixture_id,
            season=_safe_int(league_data.get("season")),
            league=league_data.get("name") or "Unknown Competition",
            home_team=home_name,
            away_team=away_name,
            kickoff_date=kickoff_datetime.date(),
        )
        session.add(match)
        session.flush()

    match.competition_id = competition.id if competition else None
    match.home_team_id = home_team.id if home_team else None
    match.away_team_id = away_team.id if away_team else None

    match.season = _safe_int(league_data.get("season"))
    match.league = league_data.get("name") or match.league

    match.home_team = home_name
    match.away_team = away_name

    match.kickoff_date = kickoff_datetime.date()
    match.kickoff_datetime = kickoff_datetime

    match.status = status_short
    match.round_name = league_data.get("round")

    match.home_goals = goals_data.get("home")
    match.away_goals = goals_data.get("away")

    match.is_finished = status_short in FINISHED_STATUSES
    match.is_postponed = status_short in POSTPONED_STATUSES
    match.is_cancelled = status_short in CANCELLED_STATUSES

    match.has_stats = False
    match.is_valid_for_training = (
        match.is_finished
        and match.home_goals is not None
        and match.away_goals is not None
        and not match.is_cancelled
        and not match.is_postponed
    )

    match.last_synced_at = datetime.utcnow()

    session.flush()

    _ensure_placeholder_team_stats(
        session=session,
        match=match,
        home_team_name=home_name,
        away_team_name=away_name,
    )

    session.commit()

    return "inserted" if is_new else "updated"


def _ensure_placeholder_team_stats(
    session: Session,
    match: Match,
    home_team_name: str,
    away_team_name: str,
) -> None:
    existing_home = session.scalar(
        select(TeamMatchStat).where(
            TeamMatchStat.match_id == match.id,
            TeamMatchStat.is_home == 1,
        )
    )

    existing_away = session.scalar(
        select(TeamMatchStat).where(
            TeamMatchStat.match_id == match.id,
            TeamMatchStat.is_home == 0,
        )
    )

    if existing_home is None:
        session.add(
            TeamMatchStat(
                match_id=match.id,
                team=home_team_name,
                is_home=1,
                goals=0,
                corners=0,
                shots_on_target=0,
                possession=0.0,
                fouls=0,
                cards=0,
                keeper_saves=0,
            )
        )
    else:
        existing_home.team = home_team_name

    if existing_away is None:
        session.add(
            TeamMatchStat(
                match_id=match.id,
                team=away_team_name,
                is_home=0,
                goals=0,
                corners=0,
                shots_on_target=0,
                possession=0.0,
                fouls=0,
                cards=0,
                keeper_saves=0,
            )
        )
    else:
        existing_away.team = away_team_name


def _get_or_create_country(
    session: Session,
    name: str | None,
) -> Country | None:
    if not name:
        return None

    country = session.scalar(
        select(Country).where(Country.name == name)
    )

    if country:
        return country

    country = Country(
        name=name,
        code=None,
        continent=None,
    )

    session.add(country)
    session.flush()

    return country


def _get_or_create_competition(
    session: Session,
    country_id: int | None,
    league_data: dict[str, Any],
) -> Competition | None:
    league_id = league_data.get("id")
    name = league_data.get("name")

    if league_id is None or not name:
        return None

    provider_competition_id = str(league_id)

    competition = session.scalar(
        select(Competition).where(
            Competition.provider == "api-football",
            Competition.provider_competition_id == provider_competition_id,
        )
    )

    if competition:
        competition.name = name
        competition.country_id = country_id
        competition.is_cup = _guess_is_cup(name)
        return competition

    competition = Competition(
        sport="football",
        provider="api-football",
        provider_competition_id=provider_competition_id,
        name=name,
        country_id=country_id,
        competition_type=None,
        is_cup=_guess_is_cup(name),
        is_active=True,
    )

    session.add(competition)
    session.flush()

    return competition


def _get_or_create_team(
    session: Session,
    country_id: int | None,
    team_data: dict[str, Any],
) -> Team | None:
    team_id = team_data.get("id")
    name = team_data.get("name")

    if team_id is None or not name:
        return None

    provider_team_id = str(team_id)

    team = session.scalar(
        select(Team).where(
            Team.provider == "api-football",
            Team.provider_team_id == provider_team_id,
        )
    )

    if team:
        team.name = name
        team.normalized_name = _normalize_name(name)
        team.country_id = country_id
        return team

    team = Team(
        provider="api-football",
        provider_team_id=provider_team_id,
        name=name,
        normalized_name=_normalize_name(name),
        country_id=country_id,
        is_national_team=False,
    )

    session.add(team)
    session.flush()

    return team


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        cleaned = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_name(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _guess_is_cup(name: str) -> bool:
    lowered = name.lower()

    cup_keywords = [
        "cup",
        "fa cup",
        "carabao",
        "champions league",
        "europa league",
        "conference league",
        "world cup",
        "afcon",
        "copa",
        "copa del rey",
        "coppa",
        "dfb pokal",
    ]

    return any(keyword in lowered for keyword in cup_keywords)