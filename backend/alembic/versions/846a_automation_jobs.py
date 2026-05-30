"""add automation jobs

Revision ID: 846a_automation_jobs
Revises: 845a_execution_market_intelligence
Create Date: 2026-05-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "846a_automation_jobs"
down_revision = "845a_execution_market_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_key", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cron_expression", sa.String(length=120), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("job_key", name="uq_automation_jobs_job_key"),
    )

    op.create_index(
        "ix_automation_jobs_job_key",
        "automation_jobs",
        ["job_key"],
    )

    op.create_table(
        "automation_job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_key", sa.String(length=120), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="running"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("command_count", sa.Integer(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_automation_job_runs_job_key",
        "automation_job_runs",
        ["job_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_automation_job_runs_job_key",
        table_name="automation_job_runs",
    )

    op.drop_table("automation_job_runs")

    op.drop_index(
        "ix_automation_jobs_job_key",
        table_name="automation_jobs",
    )

    op.drop_table("automation_jobs")