"""upgrade automation job runs

Revision ID: 847a_automation_job_progress
Revises: 846a_automation_jobs
Create Date: 2026-05-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "847a_automation_job_progress"
down_revision = "846a_automation_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_job_runs",
        sa.Column("progress_percent", sa.Float(), nullable=True, server_default="0"),
    )
    op.add_column(
        "automation_job_runs",
        sa.Column("current_step", sa.String(length=240), nullable=True),
    )
    op.add_column(
        "automation_job_runs",
        sa.Column("command_log", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_job_runs", "command_log")
    op.drop_column("automation_job_runs", "current_step")
    op.drop_column("automation_job_runs", "progress_percent")