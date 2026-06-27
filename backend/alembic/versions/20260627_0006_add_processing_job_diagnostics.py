"""add processing job diagnostics

Revision ID: 20260627_0006
Revises: 20260627_0005
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260627_0006"
down_revision: str | None = "20260627_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("processing_jobs", sa.Column("diagnostics", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("processing_jobs", "diagnostics")
