# backend/app/ingest/football_stats_ingestion.py

from datetime import datetime
import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Match, TeamMatchStat
from app.ingest.api_football_client import ApiFootballClient


MAX_STATS_ATTEMPTS = 1


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
    force: bool = False,
    half: int | None = None,
) -> dict:
    match = session.get(Match, match_id)

    if match is None:
        raise ValueError("Match not found.")

    existing_real_stats = _existing_real_stats_count(
        session=session,
        match_id=match.id,
    )

    if existing_real_stats >= 2 and not force and half is None:
        match.has_stats = True
        match.stats_unavailable = False
        session.commit()

        return {
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "skipped": True,
            "reason": "real stats already exist locally; fixed has_stats without API call",
            "api_team_blocks": 0,
            "teams_updated": 0,
            "blocks_with_real_stats": existing_real_stats,
            "has_stats": True,
            "stats_unavailable": False,
            "stats_attempt_count": int(match.stats_attempt_count or 0),
            "updated_at": datetime.utcnow().isoformat(),
        }

    eligibility = _stats_ingestion_eligibility(
        match=match,
        force=force,
    )

    if not eligibility["eligible"]:
        return {
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "skipped": True,
            "reason": eligibility["reason"],
            "api_team_blocks": 0,
            "teams_updated": 0,
            "blocks_with_real_stats": 0,
            "has_stats": bool(match.has_stats),
            "stats_unavailable": bool(getattr(match, "stats_unavailable", False)),
            "stats_attempt_count": int(getattr(match, "stats_attempt_count", 0) or 0),
            "updated_at": datetime.utcnow().isoformat(),
        }

    existing_stats = list(
        session.scalars(
            select(TeamMatchStat).where(
                TeamMatchStat.match_id == match.id,
            )
        )
    )

    if not existing_stats:
        match.stats_attempted_at = datetime.utcnow()
        match.stats_attempt_count = int(match.stats_attempt_count or 0) + 1
        match.stats_unavailable = True
        match.last_synced_at = datetime.utcnow()
        session.commit()

        return {
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "skipped": True,
            "reason": "no TeamMatchStat rows found for this match",
            "api_team_blocks": 0,
            "teams_updated": 0,
            "blocks_with_real_stats": 0,
            "has_stats": False,
            "stats_unavailable": True,
            "stats_attempt_count": int(match.stats_attempt_count or 0),
            "updated_at": datetime.utcnow().isoformat(),
        }

    match.stats_attempted_at = datetime.utcnow()
    match.stats_attempt_count = int(match.stats_attempt_count or 0) + 1
    session.commit()

    client = ApiFootballClient(session=session)

    payload = client.get_fixture_statistics(
        fixture_id=str(match.provider_fixture_id),
        half=half,
    )

    rows = payload.get("response", [])

    if not isinstance(rows, list):
        raise ValueError("Invalid statistics response.")

    if len(rows) == 0:
        match.has_stats = False
        match.stats_unavailable = True
        match.last_synced_at = datetime.utcnow()
        session.commit()

        return {
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "skipped": False,
            "reason": "api returned empty statistics response; marked stats_unavailable",
            "api_team_blocks": 0,
            "teams_updated": 0,
            "blocks_with_real_stats": 0,
            "has_stats": False,
            "stats_unavailable": True,
            "stats_attempt_count": int(match.stats_attempt_count or 0),
            "updated_at": datetime.utcnow().isoformat(),
        }

    updated_teams = 0
    blocks_with_real_stats = 0
    unmatched_api_teams: list[str] = []

    for team_block in rows:
        team_info = team_block.get("team") or {}
        statistics = team_block.get("statistics") or []

        api_team_name = team_info.get("name")

        if not api_team_name:
            continue

        stat_row = _find_matching_stat_row(
            api_team_name=api_team_name,
            match=match,
            existing_stats=existing_stats,
        )

        if stat_row is None:
            unmatched_api_teams.append(api_team_name)
            continue

        parsed = _parse_statistics(statistics)

        if parsed["_real_fields_seen"] <= 0:
            continue

        stat_row.shots_on_target = parsed["shots_on_target"]
        stat_row.corners = parsed["corners"]
        stat_row.possession = parsed["possession"]
        stat_row.fouls = parsed["fouls"]
        stat_row.cards = parsed["cards"]
        stat_row.keeper_saves = parsed["keeper_saves"]

        stat_row.source = "api_football"
        stat_row.is_real = True
        stat_row.raw_stats_json = team_block
        stat_row.updated_at = datetime.utcnow()

        updated_teams += 1
        blocks_with_real_stats += 1

    if updated_teams >= 2 and blocks_with_real_stats >= 2:
        match.has_stats = True
        match.stats_unavailable = False
        reason = "real stats saved for both teams"
    else:
        match.has_stats = False
        match.stats_unavailable = True

        if unmatched_api_teams:
            reason = "api teams could not be matched to local teams; marked stats_unavailable"
        else:
            reason = "api response existed but no usable real stats were saved; marked stats_unavailable"

    match.last_synced_at = datetime.utcnow()
    session.commit()

    return {
        "match_id": match.id,
        "provider_fixture_id": match.provider_fixture_id,
        "skipped": False,
        "reason": reason,
        "api_team_blocks": len(rows),
        "teams_updated": updated_teams,
        "blocks_with_real_stats": blocks_with_real_stats,
        "has_stats": bool(match.has_stats),
        "stats_unavailable": bool(match.stats_unavailable),
        "stats_attempt_count": int(match.stats_attempt_count or 0),
        "unmatched_api_teams": unmatched_api_teams,
        "updated_at": datetime.utcnow().isoformat(),
    }


def ingest_missing_statistics(
    session: Session,
    limit: int = 100,
    force: bool = False,
    season: int | None = None,
) -> dict:
    conditions = [
        Match.provider == "api-football",
        Match.provider_fixture_id.isnot(None),
        Match.is_finished.is_(True),
        Match.is_cancelled.is_(False),
        Match.is_postponed.is_(False),
        Match.home_goals.isnot(None),
        Match.away_goals.isnot(None),
    ]

    if season is not None:
        conditions.append(Match.season == season)

    if not force:
        conditions.extend(
            [
                Match.has_stats.is_(False),
                Match.stats_unavailable.is_(False),
                Match.stats_attempt_count < MAX_STATS_ATTEMPTS,
            ]
        )

    matches = list(
        session.scalars(
            select(Match)
            .where(*conditions)
            .order_by(
                Match.has_odds.desc(),
                Match.kickoff_date.desc(),
            )
            .limit(limit)
        )
    )

    processed = 0
    skipped = 0
    failed = 0
    unavailable = 0
    failures = []
    results = []

    for match in matches:
        try:
            result = ingest_fixture_statistics(
                session=session,
                match_id=match.id,
                force=force,
            )

            results.append(result)

            if result.get("skipped"):
                skipped += 1
            elif result.get("has_stats"):
                processed += 1
            elif result.get("stats_unavailable"):
                unavailable += 1

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

            if "Daily API safety limit reached" in str(exc):
                break

    return {
        "season": season,
        "matches_checked": len(matches),
        "matches_processed": processed,
        "matches_skipped": skipped,
        "matches_unavailable": unavailable,
        "matches_failed": failed,
        "failures": failures[:20],
        "sample_results": results[:10],
    }


def _stats_ingestion_eligibility(
    match: Match,
    force: bool = False,
) -> dict:
    if match.provider != "api-football":
        return {"eligible": False, "reason": "not an api-football match"}

    if not match.provider_fixture_id:
        return {"eligible": False, "reason": "match has no provider fixture ID"}

    if match.is_cancelled:
        return {"eligible": False, "reason": "match is cancelled"}

    if match.is_postponed:
        return {"eligible": False, "reason": "match is postponed"}

    if not match.is_finished:
        return {"eligible": False, "reason": "match is not finished"}

    if match.home_goals is None or match.away_goals is None:
        return {"eligible": False, "reason": "finished match has missing score"}

    if match.has_stats and not force:
        return {"eligible": False, "reason": "match already has real stats"}

    if getattr(match, "stats_unavailable", False) and not force:
        return {"eligible": False, "reason": "stats previously unavailable"}

    if int(getattr(match, "stats_attempt_count", 0) or 0) >= MAX_STATS_ATTEMPTS and not force:
        return {"eligible": False, "reason": "stats already attempted once"}

    return {"eligible": True, "reason": "eligible"}


def _existing_real_stats_count(
    session: Session,
    match_id: int,
) -> int:
    rows = list(
        session.scalars(
            select(TeamMatchStat.id)
            .where(
                TeamMatchStat.match_id == match_id,
                TeamMatchStat.is_real.is_(True),
            )
            .limit(2)
        )
    )

    return len(rows)


def _find_matching_stat_row(
    api_team_name: str,
    match: Match,
    existing_stats: list[TeamMatchStat],
) -> TeamMatchStat | None:
    api_norm = _normalize_team_name(api_team_name)

    for stat_row in existing_stats:
        if _normalize_team_name(stat_row.team) == api_norm:
            return stat_row

    home_norm = _normalize_team_name(match.home_team)
    away_norm = _normalize_team_name(match.away_team)

    if _names_match(api_norm, home_norm):
        return _stat_row_by_side(existing_stats, is_home=1)

    if _names_match(api_norm, away_norm):
        return _stat_row_by_side(existing_stats, is_home=0)

    candidates = []

    for stat_row in existing_stats:
        score = SequenceMatcher(
            None,
            api_norm,
            _normalize_team_name(stat_row.team),
        ).ratio()

        candidates.append((score, stat_row))

    candidates.sort(key=lambda item: item[0], reverse=True)

    if candidates and candidates[0][0] >= 0.82:
        return candidates[0][1]

    return None


def _stat_row_by_side(
    existing_stats: list[TeamMatchStat],
    is_home: int,
) -> TeamMatchStat | None:
    for stat_row in existing_stats:
        if int(stat_row.is_home) == is_home:
            return stat_row

    return None


def _names_match(left: str, right: str) -> bool:
    if not left or not right:
        return False

    if left == right:
        return True

    if left in right or right in left:
        return True

    return SequenceMatcher(None, left, right).ratio() >= 0.82


def _normalize_team_name(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower().strip()
    value = re.sub(r"\b(fc|sc|cf|afc|club|football club)\b", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


def _parse_statistics(stat_rows: list[dict]) -> dict:
    parsed = {
        "shots_on_target": 0,
        "corners": 0,
        "possession": 0.0,
        "fouls": 0,
        "cards": 0,
        "keeper_saves": 0,
        "_real_fields_seen": 0,
    }

    yellow_cards = 0
    red_cards = 0

    for row in stat_rows:
        stat_type = row.get("type")
        raw_value = row.get("value")

        if stat_type == "Yellow Cards":
            if raw_value is not None:
                parsed["_real_fields_seen"] += 1
            yellow_cards = _safe_int(raw_value)
            continue

        if stat_type == "Red Cards":
            if raw_value is not None:
                parsed["_real_fields_seen"] += 1
            red_cards = _safe_int(raw_value)
            continue

        field_name = STAT_NAME_MAP.get(stat_type)

        if not field_name:
            continue

        if raw_value is not None:
            parsed["_real_fields_seen"] += 1

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