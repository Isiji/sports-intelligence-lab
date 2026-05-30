# backend/app/services/automation_job_service.py

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    AutomationJob,
    AutomationJobRun,
)

from app.services.admin_command_service import (
    run_admin_command,
)


JOB_TO_ADMIN_COMMAND = {
    # =====================================================
    # DAILY PRODUCTION
    # =====================================================

    "daily_safe_pipeline":
        "daily_safe_1000",

    "overnight_safe_pipeline":
        "overnight_safe_3000",

    # =====================================================
    # INGESTION
    # =====================================================

    "adaptive_stats_refresh":
        "daily_safe_1000",

    "missing_stats_refresh":
        "daily_safe_1000",

    "odds_upcoming_refresh":
        "daily_safe_1000",

    "odds_finished_refresh":
        "daily_safe_1000",

    # =====================================================
    # SETTLEMENT
    # =====================================================

    "settlement_cycle":
        "settle_finished_execution",

    # =====================================================
    # INTELLIGENCE
    # =====================================================

    "intelligence_rebuild":
        "rebuild_all_intelligence",

    "production_review_refresh":
        "profitability_reports_full",

    # =====================================================
    # TRAINING
    # =====================================================

    "weekly_training":
        "train_all_models_safe",

    "feature_rebuild":
        "rebuild_features_only",

    # =====================================================
    # BACKTESTING
    # =====================================================

    "weekly_backtest":
        "backtest_all_core_markets",

    "expanded_backtest":
        "backtest_all_expanded_markets",

    "cached_group_backtest":
        "cached_group_backtest_safe",

    # =====================================================
    # RESEARCH
    # =====================================================

    "full_research_cycle":
        "full_research_cycle",
}


class AutomationJobService:

    @staticmethod
    def ensure_default_jobs(
        session: Session,
    ) -> None:

        defaults = [

            # ==========================================
            # DAILY
            # ==========================================

            (
                "daily_safe_pipeline",
                "0 2 * * *",
            ),

            (
                "overnight_safe_pipeline",
                "0 3 * * *",
            ),

            (
                "settlement_cycle",
                "*/30 * * * *",
            ),

            (
                "production_review_refresh",
                "0 */4 * * *",
            ),

            # ==========================================
            # INGESTION
            # ==========================================

            (
                "adaptive_stats_refresh",
                "0 1 * * *",
            ),

            (
                "missing_stats_refresh",
                "30 1 * * *",
            ),

            (
                "odds_finished_refresh",
                "0 */2 * * *",
            ),

            (
                "odds_upcoming_refresh",
                "15 */2 * * *",
            ),

            # ==========================================
            # WEEKLY
            # ==========================================

            (
                "weekly_training",
                "0 1 * * 0",
            ),

            (
                "weekly_backtest",
                "0 4 * * 0",
            ),

            (
                "expanded_backtest",
                "0 8 * * 0",
            ),

            (
                "full_research_cycle",
                "0 12 * * 0",
            ),
        ]

        for key, cron in defaults:

            existing = (
                session.query(AutomationJob)
                .filter(
                    AutomationJob.job_key == key,
                )
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
    def list_jobs(
        session: Session,
    ) -> list[AutomationJob]:

        return (
            session.query(
                AutomationJob,
            )
            .order_by(
                AutomationJob.job_key,
            )
            .all()
        )

    @staticmethod
    def set_enabled(
        session: Session,
        job_key: str,
        enabled: bool,
    ) -> dict[str, Any]:

        job = (
            session.query(
                AutomationJob,
            )
            .filter(
                AutomationJob.job_key == job_key,
            )
            .first()
        )

        if not job:
            return {
                "ok": False,
                "error": "Job not found",
            }

        job.enabled = enabled

        session.commit()

        return {
            "ok": True,
            "job_key": job_key,
            "enabled": enabled,
        }

    @staticmethod
    def run_job_now(
        session: Session,
        job_key: str,
    ) -> dict[str, Any]:

        command_key = JOB_TO_ADMIN_COMMAND.get(
            job_key,
        )

        if not command_key:
            return {
                "ok": False,
                "error": f"Unknown job: {job_key}",
            }

        run = AutomationJobRun(
            job_key=job_key,
            started_at=datetime.utcnow(),
            status="running",
        )

        session.add(run)
        session.commit()

        try:

            result = run_admin_command(
                command_key,
            )

            finished = datetime.utcnow()

            run.status = "success"
            run.finished_at = finished
            run.output = str(result)

            run.duration_seconds = (
                finished -
                run.started_at
            ).total_seconds()

            job = (
                session.query(
                    AutomationJob,
                )
                .filter(
                    AutomationJob.job_key == job_key,
                )
                .first()
            )

            if job:
                job.last_run_at = finished
                job.last_status = "success"

            session.commit()

            return {
                "ok": True,
                "job_key": job_key,
                "result": result,
            }

        except Exception as exc:

            finished = datetime.utcnow()

            run.status = "failed"
            run.error = str(exc)
            run.finished_at = finished

            run.duration_seconds = (
                finished -
                run.started_at
            ).total_seconds()

            job = (
                session.query(
                    AutomationJob,
                )
                .filter(
                    AutomationJob.job_key == job_key,
                )
                .first()
            )

            if job:
                job.last_run_at = finished
                job.last_status = "failed"

            session.commit()

            return {
                "ok": False,
                "error": str(exc),
            }

    @staticmethod
    def recent_runs(
        session: Session,
        limit: int = 50,
    ) -> list[AutomationJobRun]:

        return (
            session.query(
                AutomationJobRun,
            )
            .order_by(
                AutomationJobRun.started_at.desc(),
            )
            .limit(limit)
            .all()
        )