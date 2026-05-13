# backend/app/services/overnight_pipeline_service.py

import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.api_budget_allocator import ApiBudgetAllocator
from app.services.league_decay_service import LeagueDecayService
from app.services.model_drift_service import ModelDriftService


class OvernightPipelineService:
    """
    Autonomous overnight orchestration pipeline.

    Runs:
    1. stale league decay
    2. missing stats ingestion
    3. finished odds ingestion
    4. upcoming odds ingestion
    5. ecosystem-driven odds expansion
    6. ELO rebuild
    7. feature rebuild
    8. intelligence rebuild
    9. drift check
    10. optional retraining
    11. predictions
    12. grouping

    Production-safe defaults.
    """

    def __init__(
        self,
        session: Session,
        daily_api_limit: int = 7000,
        safety_reserve: int = 700,
        dry_run: bool = False,
    ):
        self.session = session
        self.daily_api_limit = daily_api_limit
        self.safety_reserve = safety_reserve
        self.dry_run = dry_run
        self.project_root = Path.cwd()

    def run(self) -> dict:
        started_at = datetime.utcnow().isoformat()

        budget_plan = ApiBudgetAllocator(
            daily_limit=self.daily_api_limit,
            safety_reserve=self.safety_reserve,
        ).build_plan()

        results: list[dict] = []

        decay_result = LeagueDecayService().mark_stale_leagues(self.session)
        results.append({"step": "league_decay", "result": decay_result})

        commands = self._build_commands(budget_plan)

        for name, command in commands:
            result = self._run_command(name, command)
            results.append(result)

        drift = ModelDriftService().check_drift(self.session)
        results.append({"step": "model_drift_check", "result": drift.__dict__})

        if drift.should_retrain:
            results.append(
                self._run_command(
                    "train_football",
                    ["python", "-m", "app.cli", "train-football"],
                )
            )

        results.append(
            self._run_command(
                "predict_football",
                ["python", "-m", "app.cli", "predict-football"],
            )
        )

        results.append(
            self._run_command(
                "group_predictions",
                ["python", "-m", "app.cli", "group-predictions", "--require-odds"],
            )
        )

        return {
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
            "dry_run": self.dry_run,
            "budget_plan": asdict(budget_plan),
            "results": results,
        }

    def _build_commands(self, budget_plan) -> list[tuple[str, list[str]]]:
        return [
            (
                "ingest_missing_stats",
                [
                    "python",
                    "-m",
                    "app.cli",
                    "ingest-missing-stats",
                    "--limit",
                    str(budget_plan.stats_budget),
                    "--force",
                ],
            ),
            (
                "ingest_finished_odds",
                [
                    "python",
                    "-m",
                    "app.cli",
                    "ingest-odds-finished",
                    "--limit",
                    str(budget_plan.odds_budget),
                    "--force",
                ],
            ),
            (
                "ingest_upcoming_odds",
                [
                    "python",
                    "-m",
                    "app.cli",
                    "ingest-odds-upcoming",
                    "--limit",
                    str(budget_plan.upcoming_odds_budget),
                    "--force",
                ],
            ),
            (
                "ingest_ecosystem_odds",
                [
                    "python",
                    "-m",
                    "app.cli",
                    "ingest-ecosystem-odds",
                    "--limit",
                    str(budget_plan.discovery_budget),
                ],
            ),
            (
                "build_elo_ratings",
                ["python", "-m", "app.cli", "build-elo-ratings"],
            ),
            (
                "build_football_features",
                ["python", "-m", "app.cli", "build-football-features"],
            ),
            (
                "rebuild_market_intelligence",
                ["python", "-m", "app.cli", "rebuild-market-intelligence"],
            ),
            (
                "rebuild_league_intelligence",
                ["python", "-m", "app.cli", "rebuild-league-intelligence"],
            ),
            (
                "rebuild_league_market_intelligence",
                ["python", "-m", "app.cli", "rebuild-league-market-intelligence"],
            ),
            (
                "rebuild_odds_band_intelligence",
                ["python", "-m", "app.cli", "rebuild-odds-band-intelligence"],
            ),
            (
                "rebuild_confidence_band_intelligence",
                ["python", "-m", "app.cli", "rebuild-confidence-band-intelligence"],
            ),
        ]

    def _run_command(self, name: str, command: list[str]) -> dict:
        if self.dry_run:
            return {
                "step": name,
                "command": " ".join(command),
                "status": "DRY_RUN",
            }

        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )

            return {
                "step": name,
                "command": " ".join(command),
                "status": "SUCCESS" if completed.returncode == 0 else "FAILED",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-3000:],
                "stderr": completed.stderr[-3000:],
            }

        except Exception as exc:
            return {
                "step": name,
                "command": " ".join(command),
                "status": "ERROR",
                "error": str(exc),
            }