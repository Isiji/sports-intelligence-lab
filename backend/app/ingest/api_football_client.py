# backend/app/ingest/api_football_client.py

from datetime import date, datetime, time
from typing import Any
import time as sleep_time

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ApiCallLog


class ApiQuotaExceededError(RuntimeError):
    pass


class ApiFootballClient:
    def __init__(self, session: Session | None = None) -> None:
        if not settings.sports_api_key:
            raise ValueError("SPORTSLAB_SPORTS_API_KEY is missing in .env.")

        self.session = session
        self.base_url = settings.sports_api_base_url.rstrip("/")
        self.headers = {"x-apisports-key": settings.sports_api_key}

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_quota_available()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        params = params or {}

        for attempt in range(1, settings.sports_api_retry_attempts + 1):
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=settings.sports_api_timeout_seconds,
            )

            self._log_api_call(endpoint, params)

            if response.status_code == 429:
                if attempt < settings.sports_api_retry_attempts:
                    sleep_time.sleep(settings.sports_api_retry_sleep_seconds)
                    continue
                raise ApiQuotaExceededError("API rate limit reached.")

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("Invalid API response format.")

            return data

        raise RuntimeError("API request failed.")

    def get_leagues_by_season(self, season: int) -> dict[str, Any]:
        return self.get("leagues", {"season": season})

    def search_leagues(
        self,
        search: str,
        season: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "search": search,
        }

        if season is not None:
            params["season"] = season

        return self.get("leagues", params)

    def get_fixtures_by_date(self, date_value: str) -> dict[str, Any]:
        return self.get("fixtures", {"date": date_value})

    def get_fixtures_by_league_season(
        self,
        league_id: int,
        season: int,
        status: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"league": league_id, "season": season}

        if status:
            params["status"] = status

        return self.get("fixtures", params)

    def get_fixture_by_id(self, fixture_id: str) -> dict[str, Any]:
        return self.get("fixtures", {"id": fixture_id})

    def get_fixtures_by_ids(self, fixture_ids: list[str]) -> dict[str, Any]:
        clean_ids = [str(fixture_id) for fixture_id in fixture_ids if fixture_id]

        if not clean_ids:
            return {"response": []}

        return self.get("fixtures", {"ids": "-".join(clean_ids)})

    def get_fixture_statistics(
        self,
        fixture_id: str,
        half: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"fixture": fixture_id}

        if half is not None:
            params["half"] = half

        return self.get("fixtures/statistics", params)

    def get_injuries_by_fixture_ids(self, fixture_ids: list[str]) -> dict[str, Any]:
        clean_ids = [str(fixture_id) for fixture_id in fixture_ids if fixture_id]

        if not clean_ids:
            return {"response": []}

        return self.get("injuries", {"ids": "-".join(clean_ids)})

    def get_odds_by_fixture(self, fixture_id: str) -> dict[str, Any]:
        return self.get("odds", {"fixture": fixture_id})

    def _ensure_quota_available(self) -> None:
        if self.session is None:
            return

        used_today = self._api_calls_used_today()
        usable_limit = max(
            settings.sports_api_daily_limit - settings.sports_api_safety_buffer,
            0,
        )

        if used_today >= usable_limit:
            raise ApiQuotaExceededError(
                f"Daily API safety limit reached. Used {used_today}/{settings.sports_api_daily_limit}."
            )

    def _api_calls_used_today(self) -> int:
        if self.session is None:
            return 0

        today_start = datetime.combine(date.today(), time.min)

        query = (
            select(func.count())
            .select_from(ApiCallLog)
            .where(
                ApiCallLog.provider == "api-football",
                ApiCallLog.called_at >= today_start,
            )
        )

        return int(self.session.execute(query).scalar() or 0)

    def _log_api_call(self, endpoint: str, params: dict[str, Any]) -> None:
        if self.session is None:
            return

        compact_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        endpoint_label = f"{endpoint}?{compact_params}" if compact_params else endpoint

        self.session.add(
            ApiCallLog(
                provider="api-football",
                endpoint=endpoint_label[:120],
            )
        )
        self.session.commit()