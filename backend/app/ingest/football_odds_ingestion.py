# backend/app/ingest/football_odds_ingestion.py

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Match, MatchOdds, ProviderSyncLog
from app.ingest.api_football_client import ApiFootballClient
from app.ingest.odds_mapping import extract_line_value, normalize_market_selection


MAX_ODDS_ATTEMPTS = 1


def ingest_odds_for_fixture(
    session: Session,
    match_id: int,
    force: bool = False,
) -> dict[str, Any]:
    match = session.get(Match, match_id)

    if match is None:
        raise ValueError(f"Match {match_id} not found.")

    existing_odds_count = _existing_odds_count(session=session, match_id=match.id)

    if existing_odds_count > 0 and not force:
        match.has_odds = True
        match.odds_unavailable = False
        session.commit()

        return {
            "status": "skipped",
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "reason": "odds rows already exist locally; fixed has_odds without API call",
            "records_received": 0,
            "records_inserted": 0,
            "records_skipped": existing_odds_count,
            "odds_unavailable": False,
            "odds_attempt_count": int(match.odds_attempt_count or 0),
            "unmapped_examples": [],
        }

    eligibility = _odds_ingestion_eligibility(match=match, force=force)

    if not eligibility["eligible"]:
        return {
            "status": "skipped",
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "reason": eligibility["reason"],
            "records_received": 0,
            "records_inserted": 0,
            "records_skipped": 0,
            "odds_unavailable": bool(getattr(match, "odds_unavailable", False)),
            "odds_attempt_count": int(getattr(match, "odds_attempt_count", 0) or 0),
            "unmapped_examples": [],
        }

    client = ApiFootballClient(session=session)

    sync_log = ProviderSyncLog(
        provider="api-football",
        sync_type="odds_by_fixture",
        status="started",
    )

    session.add(sync_log)

    match.odds_attempted_at = datetime.utcnow()
    match.odds_attempt_count = int(match.odds_attempt_count or 0) + 1

    session.commit()
    session.refresh(sync_log)

    records_received = 0
    records_inserted = 0
    records_skipped = 0
    unmapped_examples: list[dict[str, Any]] = []

    try:
        payload = client.get_odds_by_fixture(str(match.provider_fixture_id))
        responses = payload.get("response", [])

        if not isinstance(responses, list):
            raise ValueError("API response field 'response' is not a list.")

        if len(responses) == 0:
            match.has_odds = False
            match.odds_unavailable = True
            match.last_synced_at = datetime.utcnow()

            sync_log.status = "success"
            sync_log.finished_at = datetime.utcnow()
            sync_log.records_received = 0
            sync_log.records_inserted = 0
            sync_log.records_updated = 0
            sync_log.records_skipped = 0

            session.commit()

            return {
                "status": "success",
                "match_id": match.id,
                "provider_fixture_id": match.provider_fixture_id,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "records_received": 0,
                "records_inserted": 0,
                "records_skipped": 0,
                "odds_unavailable": True,
                "odds_attempt_count": int(match.odds_attempt_count or 0),
                "reason": "api returned empty odds response; marked odds_unavailable",
                "unmapped_examples": [],
            }

        for response_item in responses:
            bookmakers = response_item.get("bookmakers") or []

            for bookmaker_item in bookmakers:
                bookmaker_name = bookmaker_item.get("name")
                bets = bookmaker_item.get("bets") or []

                for bet in bets:
                    provider_market = bet.get("name") or ""
                    values = bet.get("values") or []

                    for value_item in values:
                        records_received += 1

                        provider_selection = value_item.get("value") or ""
                        odds_value = _safe_float(value_item.get("odd"))
                        line_value = extract_line_value(provider_selection)

                        if odds_value is None:
                            records_skipped += 1
                            continue

                        normalized = normalize_market_selection(
                            provider_market=provider_market,
                            provider_selection=provider_selection,
                            line_value=line_value,
                        )

                        if normalized is None:
                            records_skipped += 1

                            if len(unmapped_examples) < 20:
                                unmapped_examples.append(
                                    {
                                        "provider_market": provider_market,
                                        "provider_selection": provider_selection,
                                        "line_value": line_value,
                                        "odds": odds_value,
                                    }
                                )

                            continue

                        internal_market, internal_selection = normalized

                        session.add(
                            MatchOdds(
                                match_id=match.id,
                                provider="api-football",
                                bookmaker=bookmaker_name,
                                market=internal_market,
                                selection=internal_selection,
                                odds=odds_value,
                                retrieved_at=datetime.utcnow(),
                            )
                        )

                        records_inserted += 1

        match.has_odds = records_inserted > 0
        match.odds_unavailable = records_inserted <= 0
        match.last_synced_at = datetime.utcnow()

        sync_log.status = "success"
        sync_log.finished_at = datetime.utcnow()
        sync_log.records_received = records_received
        sync_log.records_inserted = records_inserted
        sync_log.records_updated = 0
        sync_log.records_skipped = records_skipped

        session.commit()

        return {
            "status": "success",
            "match_id": match.id,
            "provider_fixture_id": match.provider_fixture_id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "records_received": records_received,
            "records_inserted": records_inserted,
            "records_skipped": records_skipped,
            "odds_unavailable": bool(match.odds_unavailable),
            "odds_attempt_count": int(match.odds_attempt_count or 0),
            "unmapped_examples": unmapped_examples,
        }

    except Exception as exc:
        sync_log.status = "failed"
        sync_log.finished_at = datetime.utcnow()
        sync_log.error_message = str(exc)

        session.commit()
        raise


def ingest_odds_for_upcoming_matches(
    session: Session,
    limit: int = 20,
    force: bool = False,
    days_ahead: int = 3,
) -> dict[str, Any]:
    now = datetime.utcnow()
    max_kickoff = now + timedelta(days=days_ahead)

    conditions = [
        Match.provider == "api-football",
        Match.provider_fixture_id.isnot(None),
        Match.is_finished.is_(False),
        Match.is_cancelled.is_(False),
        Match.is_postponed.is_(False),
        Match.kickoff_datetime.isnot(None),
        Match.kickoff_datetime >= now,
        Match.kickoff_datetime <= max_kickoff,
    ]

    if not force:
        conditions.extend(
            [
                Match.has_odds.is_(False),
                Match.odds_unavailable.is_(False),
                Match.odds_attempt_count < MAX_ODDS_ATTEMPTS,
            ]
        )

    matches = list(
        session.scalars(
            select(Match)
            .where(*conditions)
            .order_by(Match.kickoff_datetime.asc())
            .limit(limit)
        )
    )

    return _ingest_odds_for_matches(
        session=session,
        matches=matches,
        force=force,
    )


def ingest_odds_for_finished_matches(
    session: Session,
    limit: int = 50,
    force: bool = False,
) -> dict[str, Any]:
    conditions = [
        Match.provider == "api-football",
        Match.provider_fixture_id.isnot(None),
        Match.is_finished.is_(True),
        Match.is_cancelled.is_(False),
        Match.is_postponed.is_(False),
        Match.home_goals.isnot(None),
        Match.away_goals.isnot(None),
    ]

    if not force:
        conditions.extend(
            [
                Match.has_odds.is_(False),
                Match.odds_unavailable.is_(False),
                Match.odds_attempt_count < MAX_ODDS_ATTEMPTS,
            ]
        )

    matches = list(
        session.scalars(
            select(Match)
            .where(*conditions)
            .order_by(Match.kickoff_datetime.desc().nulls_last())
            .limit(limit)
        )
    )

    return _ingest_odds_for_matches(
        session=session,
        matches=matches,
        force=force,
    )


def _ingest_odds_for_matches(
    session: Session,
    matches: list[Match],
    force: bool = False,
) -> dict[str, Any]:
    processed = 0
    inserted = 0
    skipped = 0
    unavailable = 0
    failed = 0
    failures: list[dict[str, Any]] = []
    unmapped_examples: list[dict[str, Any]] = []
    sample_results: list[dict[str, Any]] = []

    for match in matches:
        try:
            result = ingest_odds_for_fixture(
                session=session,
                match_id=match.id,
                force=force,
            )

            if len(sample_results) < 10:
                sample_results.append(result)

            if result.get("status") == "skipped":
                skipped += 1
                continue

            processed += 1
            inserted += int(result["records_inserted"])
            skipped += int(result["records_skipped"])

            if result.get("odds_unavailable"):
                unavailable += 1

            for example in result.get("unmapped_examples", []):
                if len(unmapped_examples) < 30:
                    unmapped_examples.append(example)

        except Exception as exc:
            failed += 1
            session.rollback()

            if len(failures) < 20:
                failures.append(
                    {
                        "match_id": match.id,
                        "provider_fixture_id": match.provider_fixture_id,
                        "home_team": match.home_team,
                        "away_team": match.away_team,
                        "error": str(exc),
                    }
                )

            if "Daily API safety limit reached" in str(exc):
                break

    return {
        "matches_found": len(matches),
        "matches_processed": processed,
        "odds_inserted": inserted,
        "odds_skipped": skipped,
        "odds_unavailable": unavailable,
        "matches_failed": failed,
        "failures": failures,
        "unmapped_examples": unmapped_examples,
        "sample_results": sample_results,
    }


def _odds_ingestion_eligibility(match: Match, force: bool = False) -> dict[str, Any]:
    if match.provider != "api-football":
        return {"eligible": False, "reason": "not an api-football match"}

    if not match.provider_fixture_id:
        return {"eligible": False, "reason": "match has no provider fixture ID"}

    if match.is_cancelled:
        return {"eligible": False, "reason": "match is cancelled"}

    if match.is_postponed:
        return {"eligible": False, "reason": "match is postponed"}

    if match.has_odds and not force:
        return {"eligible": False, "reason": "match already has odds"}

    if getattr(match, "odds_unavailable", False) and not force:
        return {"eligible": False, "reason": "odds previously unavailable"}

    if int(getattr(match, "odds_attempt_count", 0) or 0) >= MAX_ODDS_ATTEMPTS and not force:
        return {"eligible": False, "reason": "odds already attempted once"}

    return {"eligible": True, "reason": "eligible"}


def _existing_odds_count(session: Session, match_id: int) -> int:
    rows = list(
        session.scalars(
            select(MatchOdds.id).where(MatchOdds.match_id == match_id).limit(1)
        )
    )

    return len(rows)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None