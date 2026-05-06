from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Match, MatchOdds, ProviderSyncLog
from app.ingest.api_football_client import ApiFootballClient
from app.ingest.odds_mapping import extract_line_value, normalize_market_selection


def ingest_odds_for_fixture(session: Session, match_id: int) -> dict[str, Any]:
    match = session.get(Match, match_id)

    if match is None:
        raise ValueError(f"Match {match_id} not found.")

    if match.provider != "api-football" or not match.provider_fixture_id:
        raise ValueError("Odds ingestion only supports api-football fixtures.")

    client = ApiFootballClient()

    sync_log = ProviderSyncLog(
        provider="api-football",
        sync_type="odds_by_fixture",
        status="started",
    )

    session.add(sync_log)
    session.commit()
    session.refresh(sync_log)

    records_received = 0
    records_inserted = 0
    records_skipped = 0
    unmapped_examples: list[dict[str, Any]] = []

    try:
        payload = client.get(
            endpoint="odds",
            params={"fixture": match.provider_fixture_id},
        )

        responses = payload.get("response", [])

        if not isinstance(responses, list):
            raise ValueError("API response field 'response' is not a list.")

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
            "unmapped_examples": unmapped_examples,
        }

    except Exception as exc:
        sync_log.status = "failed"
        sync_log.finished_at = datetime.utcnow()
        sync_log.error_message = str(exc)
        session.commit()
        raise


def ingest_odds_for_upcoming_matches(session: Session, limit: int = 20) -> dict[str, Any]:
    matches = list(
        session.scalars(
            select(Match)
            .where(
                Match.provider == "api-football",
                Match.provider_fixture_id.isnot(None),
                Match.is_finished.is_(False),
                Match.is_cancelled.is_(False),
                Match.is_postponed.is_(False),
            )
            .order_by(Match.kickoff_datetime.asc().nulls_last())
            .limit(limit)
        )
    )

    processed = 0
    inserted = 0
    skipped = 0
    failed = 0
    failures: list[dict[str, Any]] = []
    unmapped_examples: list[dict[str, Any]] = []

    for match in matches:
        try:
            result = ingest_odds_for_fixture(
                session=session,
                match_id=match.id,
            )

            processed += 1
            inserted += int(result["records_inserted"])
            skipped += int(result["records_skipped"])

            for example in result.get("unmapped_examples", []):
                if len(unmapped_examples) < 30:
                    unmapped_examples.append(example)

        except Exception as exc:
            failed += 1

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

    return {
        "matches_found": len(matches),
        "matches_processed": processed,
        "odds_inserted": inserted,
        "odds_skipped": skipped,
        "matches_failed": failed,
        "failures": failures,
        "unmapped_examples": unmapped_examples,
    }


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None