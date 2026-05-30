# backend/app/services/automation_scheduler_service.py

from __future__ import annotations

import threading
import time
from datetime import datetime

from croniter import croniter
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import AutomationJob, AutomationJobRun
from app.services.automation_job_service import AutomationJobService


_scheduler_started = False
_scheduler_lock = threading.Lock()
_job_run_lock = threading.Lock()


def _utc_now() -> datetime:
    return datetime.utcnow()


def _calculate_next_run(
    cron_expression: str,
    base_time: datetime | None = None,
) -> datetime:
    base = base_time or _utc_now()

    return croniter(
        cron_expression,
        base,
    ).get_next(datetime)


def _has_running_job(
    session: Session,
) -> bool:
    running = (
        session.query(AutomationJobRun)
        .filter(
            AutomationJobRun.status == "running",
        )
        .first()
    )

    return running is not None


def _sync_next_run_times(
    session: Session,
) -> None:
    jobs = (
        session.query(AutomationJob)
        .filter(
            AutomationJob.enabled == True,  # noqa: E712
        )
        .all()
    )

    now = _utc_now()

    for job in jobs:
        if not job.cron_expression:
            continue

        if job.next_run_at is None:
            job.next_run_at = _calculate_next_run(
                job.cron_expression,
                now,
            )

    session.commit()


def _run_due_jobs_once() -> None:
    with _job_run_lock:
        session = SessionLocal()

        try:
            AutomationJobService.ensure_default_jobs(session)
            _sync_next_run_times(session)

            now = _utc_now()

            due_jobs = (
                session.query(AutomationJob)
                .filter(
                    AutomationJob.enabled == True,  # noqa: E712
                    AutomationJob.next_run_at != None,  # noqa: E711
                    AutomationJob.next_run_at <= now,
                )
                .order_by(
                    AutomationJob.next_run_at.asc(),
                )
                .all()
            )

            if not due_jobs:
                return

            if _has_running_job(session):
                return

            job = due_jobs[0]

            result = AutomationJobService.run_job_now(
                session=session,
                job_key=job.job_key,
            )

            refreshed_job = (
                session.query(AutomationJob)
                .filter(
                    AutomationJob.job_key == job.job_key,
                )
                .first()
            )

            if refreshed_job and refreshed_job.cron_expression:
                refreshed_job.next_run_at = _calculate_next_run(
                    refreshed_job.cron_expression,
                    now,
                )

                if result.get("ok"):
                    refreshed_job.last_status = "success"
                else:
                    refreshed_job.last_status = "failed"

            session.commit()

        finally:
            session.close()


def _scheduler_loop(
    poll_seconds: int,
) -> None:
    while True:
        try:
            _run_due_jobs_once()

        except Exception:
            pass

        time.sleep(poll_seconds)


def start_automation_scheduler(
    poll_seconds: int = 60,
) -> None:
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            return

        thread = threading.Thread(
            target=_scheduler_loop,
            args=(poll_seconds,),
            daemon=True,
        )

        thread.start()

        _scheduler_started = True