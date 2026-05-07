# backend/app/utils/slate.py

from datetime import date


def default_football_slate() -> str:
    return f"football_{date.today().isoformat()}"


def resolve_slate(slate: str | None) -> str:
    return slate or default_football_slate()