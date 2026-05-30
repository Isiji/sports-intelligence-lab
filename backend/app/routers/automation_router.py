# backend/app/routers/automation_router.py

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.automation_job_service import AutomationJobService


router = APIRouter(
    prefix="/automation",
    tags=["Automation"],
)


class AutomationJobRequest(BaseModel):
    job_key: str


def _job_to_dict(job) -> dict:
    return {
        "id": job.id,
        "job_key": job.job_key,
        "enabled": job.enabled,
        "cron_expression": job.cron_expression,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "last_status": job.last_status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def _run_to_dict(run) -> dict:
    return {
        "id": run.id,
        "job_key": run.job_key,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "status": run.status,
        "duration_seconds": run.duration_seconds,
        "command_count": run.command_count,
        "progress_percent": run.progress_percent,
        "current_step": run.current_step,
        "command_log": run.command_log or [],
        "output": run.output,
        "error": run.error,
    }

@router.post("/seed")
def seed_automation_jobs(
    db: Session = Depends(get_db),
) -> dict:
    AutomationJobService.ensure_default_jobs(db)

    return {
        "ok": True,
        "message": "Automation jobs seeded.",
    }


@router.get("/jobs")
def list_automation_jobs(
    db: Session = Depends(get_db),
) -> dict:
    AutomationJobService.ensure_default_jobs(db)

    jobs = AutomationJobService.list_jobs(db)

    return {
        "ok": True,
        "jobs": [
            _job_to_dict(job)
            for job in jobs
        ],
    }


@router.post("/jobs/run")
def run_automation_job(
    payload: AutomationJobRequest,
    db: Session = Depends(get_db),
) -> dict:
    return AutomationJobService.run_job_now(
        session=db,
        job_key=payload.job_key,
    )


@router.post("/jobs/enable")
def enable_automation_job(
    payload: AutomationJobRequest,
    db: Session = Depends(get_db),
) -> dict:
    return AutomationJobService.set_enabled(
        session=db,
        job_key=payload.job_key,
        enabled=True,
    )


@router.post("/jobs/disable")
def disable_automation_job(
    payload: AutomationJobRequest,
    db: Session = Depends(get_db),
) -> dict:
    return AutomationJobService.set_enabled(
        session=db,
        job_key=payload.job_key,
        enabled=False,
    )


@router.get("/history")
def automation_history(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    runs = AutomationJobService.recent_runs(
        session=db,
        limit=limit,
    )

    return {
        "ok": True,
        "runs": [
            _run_to_dict(run)
            for run in runs
        ],
    }