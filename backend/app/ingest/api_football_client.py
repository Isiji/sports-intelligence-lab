from typing import Any

import requests

from app.config import settings


class ApiFootballClient:
    def __init__(self) -> None:
        if not settings.sports_api_key:
            raise ValueError(
                "SPORTSLAB_SPORTS_API_KEY is missing in your .env file."
            )

        self.base_url = settings.sports_api_base_url.rstrip("/")
        self.headers = {
            "x-apisports-key": settings.sports_api_key,
        }

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = requests.get(
            url,
            headers=self.headers,
            params=params or {},
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError("Invalid API response format.")

        return data

    def get_fixtures_by_date(self, date_value: str) -> dict[str, Any]:
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