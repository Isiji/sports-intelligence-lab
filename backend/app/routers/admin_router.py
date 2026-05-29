# backend/app/routers/admin_router.py

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.admin_command_service import (
    list_admin_commands,
    run_admin_command,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


class RunAdminCommandRequest(BaseModel):
    command_key: str


@router.get("/commands")
def get_admin_commands() -> dict:
    return {
        "ok": True,
        "commands": list_admin_commands(),
    }


@router.post("/commands/run")
def run_admin_command_endpoint(payload: RunAdminCommandRequest) -> dict:
    return run_admin_command(payload.command_key)