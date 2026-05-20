# backend/app/ingest/football_ingestion.py

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.services.tournament_context_service import resolve_tournament_context

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
CANCELLED_STATUSES = {"CANC", "CANCELLED", "ABD", "SUSP", "AWD", "WO"}


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
            result = _upsert_fixture(session=session, item=item)

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
        session.rollback()

        sync_log.status = "failed"
        sync_log.finished_at = datetime.utcnow()
        sync_log.error_message = str(exc)
        sync_log.records_received = records_received
        sync_log.records_inserted = records_inserted
        sync_log.records_updated = records_updated
        sync_log.records_skipped = records_skipped

        session.add(sync_log)
        session.commit()
        raise


def ingest_fixtures_for_league_season(
    session: Session,
    league_id: int,
    season: int,
    status: str | None = None,
) -> dict[str, int | str]:
    client = ApiFootballClient(session=session)

    sync_log = ProviderSyncLog(
        provider="api-football",
        sync_type="fixtures_by_league_season",
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
        payload = client.get_fixtures_by_league_season(
            league_id=league_id,
            season=season,
            status=status,
        )

        fixtures = payload.get("response", [])

        if not isinstance(fixtures, list):
            raise ValueError("API response field 'response' is not a list.")

        records_received = len(fixtures)

        for index, item in enumerate(fixtures, start=1):
            result = _upsert_fixture(session=session, item=item)

            if result == "inserted":
                records_inserted += 1
            elif result == "updated":
                records_updated += 1
            else:
                records_skipped += 1

            if index % 500 == 0:
                session.flush()

        sync_log.status = "success"
        sync_log.finished_at = datetime.utcnow()
        sync_log.records_received = records_received
        sync_log.records_inserted = records_inserted
        sync_log.records_updated = records_updated
        sync_log.records_skipped = records_skipped

        session.commit()

        return {
            "status": "success",
            "league_id": league_id,
            "season": season,
            "records_received": records_received,
            "records_inserted": records_inserted,
            "records_updated": records_updated,
            "records_skipped": records_skipped,
        }

    except Exception as exc:
        session.rollback()

        sync_log.status = "failed"
        sync_log.finished_at = datetime.utcnow()
        sync_log.error_message = str(exc)

        session.add(sync_log)
        session.commit()
        raise


def ingest_all_leagues_for_season(
    session: Session,
    season: int,
    max_leagues: int | None = None,
    status: str | None = None,
) -> dict[str, int]:
    client = ApiFootballClient(session=session)

    payload = client.get_leagues_by_season(season=season)
    leagues = payload.get("response", [])

    if not isinstance(leagues, list):
        raise ValueError("API response field 'response' is not a list.")

    league_ids: list[int] = []

    for item in leagues:
        league = item.get("league") or {}
        league_id = league.get("id")

        if league_id is not None:
            league_ids.append(int(league_id))

    league_ids = sorted(set(league_ids))

    if max_leagues is not None:
        league_ids = league_ids[:max_leagues]

    leagues_processed = 0
    leagues_failed = 0
    fixtures_received = 0
    fixtures_inserted = 0
    fixtures_updated = 0
    fixtures_skipped = 0

    for league_id in league_ids:
        try:
            result = ingest_fixtures_for_league_season(
                session=session,
                league_id=league_id,
                season=season,
                status=status,
            )

            leagues_processed += 1
            fixtures_received += int(result["records_received"])
            fixtures_inserted += int(result["records_inserted"])
            fixtures_updated += int(result["records_updated"])
            fixtures_skipped += int(result["records_skipped"])

        except Exception:
            leagues_failed += 1
            session.rollback()
            continue

    return {
        "season": season,
        "leagues_found": len(league_ids),
        "leagues_processed": leagues_processed,
        "leagues_failed": leagues_failed,
        "fixtures_received": fixtures_received,
        "fixtures_inserted": fixtures_inserted,
        "fixtures_updated": fixtures_updated,
        "fixtures_skipped": fixtures_skipped,
    }


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

    status_short = fixture_data.get("status", {}).get("short") or "scheduled"
    tournament_context = resolve_tournament_context(
        league_name=league_data.get("name"),
        round_name=league_data.get("round"),
        country_name=league_data.get("country"),
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
            has_stats=False,
            has_odds=False,
            stats_attempt_count=0,
            odds_attempt_count=0,
            stats_unavailable=False,
            odds_unavailable=False,
        )
        session.add(match)
        session.flush()

    old_state = _match_state(match)

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
    match.is_international = tournament_context.is_international
    match.is_neutral_venue = tournament_context.is_neutral_venue
    match.tournament_type = tournament_context.tournament_type
    match.tournament_stage = tournament_context.tournament_stage
    match.competition_priority = tournament_context.competition_priority
    match.tournament_pressure_score = tournament_context.tournament_pressure_score


    match.home_goals = goals_data.get("home")
    match.away_goals = goals_data.get("away")

    match.is_finished = status_short in FINISHED_STATUSES
    match.is_postponed = status_short in POSTPONED_STATUSES
    match.is_cancelled = status_short in CANCELLED_STATUSES

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

    new_state = _match_state(match)

    if is_new:
        return "inserted"

    return "updated" if old_state != new_state else "skipped"


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

    country = session.scalar(select(Country).where(Country.name == name))

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


def _match_state(match: Match) -> dict[str, Any]:
    return {
        "season": match.season,
        "league": match.league,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "status": match.status,
        "round_name": match.round_name,
        "kickoff_date": match.kickoff_date,
        "kickoff_datetime": match.kickoff_datetime,
        "is_finished": bool(match.is_finished),
        "is_postponed": bool(match.is_postponed),
        "is_cancelled": bool(match.is_cancelled),
        "is_valid_for_training": bool(match.is_valid_for_training),
        "is_international": bool(match.is_international),
        "is_neutral_venue": bool(match.is_neutral_venue),
        "tournament_type": match.tournament_type,
        "tournament_stage": match.tournament_stage,
        "competition_priority": match.competition_priority,
        "tournament_pressure_score": match.tournament_pressure_score,
    }