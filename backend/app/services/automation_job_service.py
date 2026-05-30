# backend/app/services/automation_job_service.py

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AutomationJob, AutomationJobRun
from app.services.admin_command_service import (
    APPROVED_COMMANDS,
    resolve_cli_args,
)


JOB_TO_ADMIN_COMMAND = {
    "daily_safe_pipeline": "daily_safe_1000",
    "overnight_safe_pipeline": "overnight_safe_3000",
    "settlement_cycle": "settle_finished_execution",
    "adaptive_stats_refresh": "daily_safe_1000",
    "missing_stats_refresh": "daily_safe_1000",
    "odds_upcoming_refresh": "daily_safe_1000",
    "odds_finished_refresh": "daily_safe_1000",
    "intelligence_rebuild": "rebuild_all_intelligence",
    "production_review_refresh": "profitability_reports_full",
    "weekly_training": "train_all_models_safe",
    "feature_rebuild": "rebuild_features_only",
    "weekly_backtest": "backtest_all_core_markets",
    "expanded_backtest": "backtest_all_expanded_markets",
    "cached_group_backtest": "cached_group_backtest_safe",
    "full_research_cycle": "full_research_cycle",
}


HEAVY_JOBS = {
    "daily_safe_pipeline",
    "overnight_safe_pipeline",
    "weekly_training",
    "weekly_backtest",
    "expanded_backtest",
    "full_research_cycle",
}


class AutomationJobService:
    @staticmethod
    def recover_interrupted_runs(session: Session) -> None:
        runs = (
            session.query(AutomationJobRun)
            .filter(AutomationJobRun.status == "running")
            .all()
        )

        for run in runs:
            run.status = "interrupted"
            run.finished_at = datetime.utcnow()
            run.error = "Server restarted while this job was running."
            run.current_step = "Interrupted by server restart"

        session.commit()

    @staticmethod
    def ensure_default_jobs(session: Session) -> None:
        defaults = [
            ("daily_safe_pipeline", "0 2 * * *"),
            ("overnight_safe_pipeline", "0 3 * * *"),
            ("settlement_cycle", "*/30 * * * *"),
            ("production_review_refresh", "0 */4 * * *"),
            ("adaptive_stats_refresh", "0 1 * * *"),
            ("missing_stats_refresh", "30 1 * * *"),
            ("odds_finished_refresh", "0 */2 * * *"),
            ("odds_upcoming_refresh", "15 */2 * * *"),
            ("weekly_training", "0 1 * * 0"),
            ("weekly_backtest", "0 4 * * 0"),
            ("expanded_backtest", "0 8 * * 0"),
            ("full_research_cycle", "0 12 * * 0"),
        ]

        for key, cron in defaults:
            existing = (
                session.query(AutomationJob)
                .filter(AutomationJob.job_key == key)
                .first()
            )

            if existing:
                continue

            session.add(
                AutomationJob(
                    job_key=key,
                    cron_expression=cron,
                    enabled=True,
                    last_status="never_run",
                )
            )

        session.commit()

    @staticmethod
    def list_jobs(session: Session) -> list[AutomationJob]:
        return (
            session.query(AutomationJob)
            .order_by(AutomationJob.job_key)
            .all()
        )

    @staticmethod
    def set_enabled(
        session: Session,
        job_key: str,
        enabled: bool,
    ) -> dict[str, Any]:
        job = (
            session.query(AutomationJob)
            .filter(AutomationJob.job_key == job_key)
            .first()
        )

        if not job:
            return {"ok": False, "error": "Job not found"}

        job.enabled = enabled
        session.commit()

        return {
            "ok": True,
            "job_key": job_key,
            "enabled": enabled,
        }

    @staticmethod
    def _has_running_heavy_job(session: Session) -> bool:
        running = (
            session.query(AutomationJobRun)
            .filter(AutomationJobRun.status == "running")
            .all()
        )

        return any(run.job_key in HEAVY_JOBS for run in running)

    @staticmethod
    def run_job_now(
        session: Session,
        job_key: str,
    ) -> dict[str, Any]:
        command_key = JOB_TO_ADMIN_COMMAND.get(job_key)

        if not command_key:
            return {
                "ok": False,
                "error": f"Unknown job: {job_key}",
            }

        command = APPROVED_COMMANDS.get(command_key)

        if not command:
            return {
                "ok": False,
                "error": f"Admin command not found: {command_key}",
            }

        if job_key in HEAVY_JOBS and AutomationJobService._has_running_heavy_job(session):
            return {
                "ok": False,
                "error": "Another heavy automation job is already running.",
            }

        run = AutomationJobRun(
            job_key=job_key,
            started_at=datetime.utcnow(),
            status="running",
            progress_percent=0,
            current_step="Starting",
            command_count=len(command.commands),
            command_log=[],
        )

        session.add(run)
        session.commit()

        logs: list[dict[str, Any]] = []
        combined_output: list[str] = []

        try:
            total = max(len(command.commands), 1)

            for index, cli_args_template in enumerate(command.commands, start=1):
                cli_args = resolve_cli_args(cli_args_template)

                full_command = [
                    sys.executable,
                    "-m",
                    "app.cli",
                    *cli_args,
                ]

                step_name = " ".join(cli_args)

                run.current_step = step_name
                run.progress_percent = round(((index - 1) / total) * 100, 2)
                run.command_log = logs
                session.commit()

                started = datetime.utcnow()

                item = {
                    "index": index,
                    "command": " ".join(full_command),
                    "status": "running",
                    "started_at": started.isoformat(),
                    "finished_at": None,
                    "duration_seconds": None,
                    "stdout": "",
                    "stderr": "",
                }

                logs.append(item)
                run.command_log = logs
                session.commit()

                completed = subprocess.run(
                    full_command,
                    cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
                    capture_output=True,
                    text=True,
                    timeout=command.timeout_seconds,
                )

                finished = datetime.utcnow()

                item["finished_at"] = finished.isoformat()
                item["duration_seconds"] = (finished - started).total_seconds()
                item["stdout"] = completed.stdout[-4000:]
                item["stderr"] = completed.stderr[-4000:]
                item["status"] = "success" if completed.returncode == 0 else "failed"

                combined_output.append(completed.stdout)
                combined_output.append(completed.stderr)

                run.command_log = logs
                run.output = "\n".join(combined_output)[-20000:]
                run.progress_percent = round((index / total) * 100, 2)
                session.commit()

                if completed.returncode != 0:
                    raise RuntimeError(
                        f"Command failed: {step_name}\n{completed.stderr}"
                    )

            finished = datetime.utcnow()

            run.status = "success"
            run.finished_at = finished
            run.duration_seconds = (finished - run.started_at).total_seconds()
            run.progress_percent = 100
            run.current_step = "Completed"

            job = (
                session.query(AutomationJob)
                .filter(AutomationJob.job_key == job_key)
                .first()
            )

            if job:
                job.last_run_at = finished
                job.last_status = "success"

            session.commit()

            return {
                "ok": True,
                "job_key": job_key,
                "command_key": command_key,
                "steps": logs,
            }

        except Exception as exc:
            finished = datetime.utcnow()

            run.status = "failed"
            run.error = str(exc)
            run.finished_at = finished
            run.duration_seconds = (finished - run.started_at).total_seconds()
            run.command_log = logs

            job = (
                session.query(AutomationJob)
                .filter(AutomationJob.job_key == job_key)
                .first()
            )

            if job:
                job.last_run_at = finished
                job.last_status = "failed"

            session.commit()

            return {
                "ok": False,
                "job_key": job_key,
                "error": str(exc),
                "steps": logs,
            }

    @staticmethod
    def recent_runs(
        session: Session,
        limit: int = 50,
    ) -> list[AutomationJobRun]:
        return (
            session.query(AutomationJobRun)
            .order_by(AutomationJobRun.started_at.desc())
            .limit(limit)
            .all()
        )