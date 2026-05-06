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
            raise ValueError(
                "SPORTSLAB_SPORTS_API_KEY is missing in your .env file."
            )

        self.session = session
        self.base_url = settings.sports_api_base_url.rstrip("/")
        self.headers = {
            "x-apisports-key": settings.sports_api_key,
        }

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_quota_available()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        params = params or {}

        last_error: Exception | None = None

        for attempt in range(1, settings.sports_api_retry_attempts + 1):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=settings.sports_api_timeout_seconds,
                )

                self._log_api_call(
                    endpoint=endpoint,
                    params=params,
                )

                if response.status_code == 429:
                    if attempt < settings.sports_api_retry_attempts:
                        sleep_time.sleep(settings.sports_api_retry_sleep_seconds)
                        continue

                    raise ApiQuotaExceededError(
                        "API rate limit reached. Try again later or reduce batch size."
                    )

                response.raise_for_status()

                data = response.json()

                if not isinstance(data, dict):
                    raise ValueError("Invalid API response format.")

                return data

            except Exception as exc:
                last_error = exc

                if attempt < settings.sports_api_retry_attempts:
                    sleep_time.sleep(settings.sports_api_retry_sleep_seconds)
                    continue

                raise

        raise RuntimeError(str(last_error) if last_error else "Unknown API error.")

    def get_fixtures_by_date(
        self,
        date_value: str,
    ) -> dict[str, Any]:
        return self.get(
            endpoint="fixtures",
            params={
                "date": date_value,
            },
        )

    def get_fixtures_by_league_season(
        self,
        league_id: int,
        season: int,
        status: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "league": league_id,
            "season": season,
        }

        if status:
            params["status"] = status

        return self.get(
            endpoint="fixtures",
            params=params,
        )

    def get_odds_by_fixture(
        self,
        fixture_id: str,
    ) -> dict[str, Any]:
        return self.get(
            endpoint="odds",
            params={
                "fixture": fixture_id,
            },
        )

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
                f"Daily API safety limit reached. "
                f"Used {used_today}/{settings.sports_api_daily_limit}. "
                f"Safety buffer: {settings.sports_api_safety_buffer}."
            )

    def _api_calls_used_today(self) -> int:
        if self.session is None:
            return 0

        today_start = datetime.combine(
            date.today(),
            time.min,
        )

        query = select(func.count()).select_from(ApiCallLog).where(
            ApiCallLog.provider == "api-football",
            ApiCallLog.called_at >= today_start,
        )

        return int(self.session.execute(query).scalar() or 0)

    def _log_api_call(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> None:
        if self.session is None:
            return

        compact_params = "&".join(
            f"{key}={value}"
            for key, value in sorted(params.items())
        )

        endpoint_label = endpoint

        if compact_params:
            endpoint_label = f"{endpoint}?{compact_params}"

        self.session.add(
            ApiCallLog(
                provider="api-football",
                endpoint=endpoint_label[:120],
            )
        )

        self.session.commit()