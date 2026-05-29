# backend/app/routers/admin_router.py

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.admin_command_service import (
    get_active_season,
    list_admin_commands,
    run_admin_command,
    set_active_season,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


class RunAdminCommandRequest(BaseModel):
    command_key: str


class SetActiveSeasonRequest(BaseModel):
    season: int


@router.get("/season")
def get_admin_season() -> dict:
    return {
        "ok": True,
        "active_season": get_active_season(),
        "available_seasons": list(range(2032, 2021, -1)),
    }


@router.post("/season")
def set_admin_season(payload: SetActiveSeasonRequest) -> dict:
    return set_active_season(payload.season)


@router.get("/commands")
def get_admin_commands() -> dict:
    return {
        "ok": True,
        "active_season": get_active_season(),
        "commands": list_admin_commands(),
    }


@router.post("/commands/run")
def run_admin_command_endpoint(payload: RunAdminCommandRequest) -> dict:
    return run_admin_command(payload.command_key)