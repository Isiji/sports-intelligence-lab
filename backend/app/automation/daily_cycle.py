# backend/app/automation/daily_cycle.py

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass
class DailyCycleStep:
    name: str
    command: list[str]
    required: bool = True


def _run_step(step: DailyCycleStep) -> dict[str, Any]:
    print(f"\n==============================")
    print(f"STARTING: {step.name}")
    print(f"COMMAND: {' '.join(step.command)}")
    print(f"==============================")

    result = subprocess.run(
        step.command,
        capture_output=True,
        text=True,
        shell=False,
    )

    success = result.returncode == 0

    if success:
        print(f"FINISHED: {step.name}")
    else:
        print(f"FAILED: {step.name}")

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr)

    return {
        "name": step.name,
        "success": success,
        "required": step.required,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_daily_cycle(
    prediction_date: date | None = None,
    train_models: bool = False,
    ingest_limit: int = 500,
    odds_limit: int = 500,
    require_odds: bool = True,
) -> dict[str, Any]:
    selected_date = prediction_date or date.today()
    previous_date = selected_date - timedelta(days=1)

    python_cmd = sys.executable

    steps: list[DailyCycleStep] = [
        DailyCycleStep(
            name="Update finished matches",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "update-finished-matches",
                "--date",
                previous_date.isoformat(),
            ],
            required=False,
        ),
        DailyCycleStep(
            name="Ingest missing match stats",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "ingest-missing-stats",
                "--limit",
                str(ingest_limit),
                "--force",
            ],
            required=False,
        ),
        DailyCycleStep(
            name="Ingest finished odds",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "ingest-odds-finished",
                "--limit",
                str(odds_limit),
                "--force",
            ],
            required=False,
        ),
        DailyCycleStep(
            name="Build ELO ratings",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "build-elo-ratings",
            ],
        ),
        DailyCycleStep(
            name="Build football features",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "build-football-features",
            ],
        ),
        DailyCycleStep(
            name="Rebuild market intelligence",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "rebuild-market-intelligence",
            ],
            required=False,
        ),
        DailyCycleStep(
            name="Rebuild league intelligence",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "rebuild-league-intelligence",
            ],
            required=False,
        ),
        DailyCycleStep(
            name="Rebuild odds-band intelligence",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "rebuild-odds-band-intelligence",
            ],
            required=False,
        ),
        DailyCycleStep(
            name="Rebuild confidence-band intelligence",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "rebuild-confidence-band-intelligence",
            ],
            required=False,
        ),
        DailyCycleStep(
            name="Rebuild league-market intelligence",
            command=[
                python_cmd,
                "-m",
                "app.cli",
                "rebuild-league-market-intelligence",
            ],
            required=False,
        ),
    ]

    if train_models:
        steps.append(
            DailyCycleStep(
                name="Train football models",
                command=[
                    python_cmd,
                    "-m",
                    "app.cli",
                    "train-football",
                ],
            )
        )

    steps.extend(
        [
            DailyCycleStep(
                name="Ingest upcoming odds",
                command=[
                    python_cmd,
                    "-m",
                    "app.cli",
                    "ingest-odds-upcoming",
                    "--limit",
                    str(odds_limit),
                    "--force",
                ],
                required=False,
            ),
            DailyCycleStep(
                name="Predict football",
                command=[
                    python_cmd,
                    "-m",
                    "app.cli",
                    "predict-football",
                ],
            ),
            DailyCycleStep(
                name="Create production groups",
                command=[
                    python_cmd,
                    "-m",
                    "app.cli",
                    "create-groups",
                    "--require-odds",
                ]
                if require_odds
                else [
                    python_cmd,
                    "-m",
                    "app.cli",
                    "create-groups",
                ],
            ),
        ]
    )

    results: list[dict[str, Any]] = []

    for step in steps:
        result = _run_step(step)
        results.append(result)

        if step.required and not result["success"]:
            return {
                "success": False,
                "stopped_at": step.name,
                "prediction_date": selected_date.isoformat(),
                "results": results,
            }

    return {
        "success": True,
        "prediction_date": selected_date.isoformat(),
        "train_models": train_models,
        "require_odds": require_odds,
        "results": results,
    }