# backend/app/services/admin_command_service.py

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdminCommand:
    key: str
    label: str
    description: str
    commands: list[list[str]]
    api_safe_level: str = "safe"


PROJECT_BACKEND_DIR = Path(__file__).resolve().parents[2]


APPROVED_COMMANDS: dict[str, AdminCommand] = {
    "stats_light_2026": AdminCommand(
        key="stats_light_2026",
        label="Ingest Adaptive Stats 1000",
        description="Safely fills missing stats for season 2026.",
        commands=[
            ["ingest-adaptive-stats", "--limit", "1000", "--season", "2026"],
        ],
    ),
    "rebuild_match_flags": AdminCommand(
        key="rebuild_match_flags",
        label="Rebuild Match Flags",
        description="Refreshes finished/postponed/cancelled/training flags.",
        commands=[
            ["rebuild-match-flags"],
        ],
    ),
    "odds_light_2026": AdminCommand(
        key="odds_light_2026",
        label="Ingest Ecosystem Odds 1000",
        description="Production-safe ecosystem odds ingestion.",
        commands=[
            ["ingest-ecosystem-odds", "--limit", "1000", "--season", "2026"],
        ],
    ),
    "update_finished_200": AdminCommand(
        key="update_finished_200",
        label="Update Finished Matches 200",
        description="Updates finished match results without wasting calls.",
        commands=[
            ["update-finished-matches", "--limit", "200"],
        ],
    ),
    "settle_finished_execution": AdminCommand(
        key="settle_finished_execution",
        label="Settle Finished Execution Predictions",
        description="Settles all finished execution predictions.",
        commands=[
            ["settle-finished-execution-predictions"],
        ],
    ),
    "daily_safe_1000": AdminCommand(
        key="daily_safe_1000",
        label="Daily Safe Pipeline 1000",
        description="Stats, flags, odds, finished updates, and settlement.",
        commands=[
            ["ingest-adaptive-stats", "--limit", "1000", "--season", "2026"],
            ["rebuild-match-flags"],
            ["ingest-ecosystem-odds", "--limit", "1000", "--season", "2026"],
            ["update-finished-matches", "--limit", "200"],
            ["settle-finished-execution-predictions"],
        ],
    ),
    "overnight_safe_3000": AdminCommand(
        key="overnight_safe_3000",
        label="Overnight Safe Pipeline 3000",
        description="Bigger safe run: stats, finished odds, upcoming odds, flags, updates, settlement.",
        commands=[
            ["ingest-adaptive-stats", "--limit", "3000", "--season", "2026"],
            ["ingest-ecosystem-odds", "--limit", "3000", "--season", "2026", "--mode", "finished"],
            ["ingest-ecosystem-odds", "--limit", "3000", "--season", "2026", "--mode", "upcoming"],
            ["rebuild-match-flags"],
            ["update-finished-matches", "--limit", "200"],
            ["settle-finished-execution-predictions"],
        ],
    ),
}


def list_admin_commands() -> list[dict]:
    return [
        {
            "key": item.key,
            "label": item.label,
            "description": item.description,
            "api_safe_level": item.api_safe_level,
            "steps": [
                "python -m app.cli " + " ".join(command)
                for command in item.commands
            ],
        }
        for item in APPROVED_COMMANDS.values()
    ]


def run_admin_command(command_key: str) -> dict:
    command = APPROVED_COMMANDS.get(command_key)

    if command is None:
        return {
            "ok": False,
            "error": f"Unknown or unapproved admin command: {command_key}",
        }

    started = time.time()
    results = []

    for index, cli_args in enumerate(command.commands, start=1):
        full_command = [
            sys.executable,
            "-m",
            "app.cli",
            *cli_args,
        ]

        step_started = time.time()

        process = subprocess.run(
            full_command,
            cwd=str(PROJECT_BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=60 * 60,
            shell=False,
        )

        step_result = {
            "step": index,
            "command": "python -m app.cli " + " ".join(cli_args),
            "return_code": process.returncode,
            "duration_seconds": round(time.time() - step_started, 2),
            "stdout": process.stdout[-12000:],
            "stderr": process.stderr[-12000:],
            "ok": process.returncode == 0,
        }

        results.append(step_result)

        if process.returncode != 0:
            return {
                "ok": False,
                "key": command.key,
                "label": command.label,
                "duration_seconds": round(time.time() - started, 2),
                "failed_step": index,
                "results": results,
            }

    return {
        "ok": True,
        "key": command.key,
        "label": command.label,
        "duration_seconds": round(time.time() - started, 2),
        "results": results,
    }