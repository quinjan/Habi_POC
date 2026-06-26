"""create project workspaces

Revision ID: 20260626_0001
Revises:
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260626_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_workspaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("project_type", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("completion_year", sa.Integer(), nullable=True),
        sa.Column("floor_area", sa.String(length=100), nullable=True),
        sa.Column("trade_scopes", sa.JSON(), nullable=False),
        sa.Column("client_or_owner", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("project_workspaces")
