"""add reviewed evidence annotation grounding

Revision ID: 20260716_0010
Revises: 20260715_0009
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_0010"
down_revision: str | None = "20260715_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_annotations",
        sa.Column("proposal_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "evidence_annotations",
        sa.Column("source_excerpt", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "evidence_annotations",
        sa.Column("source_locator", sa.JSON(), nullable=True),
    )
    op.add_column(
        "evidence_annotations",
        sa.Column("provenance", sa.String(length=50), nullable=True),
    )
    op.execute(
        """
        UPDATE evidence_annotations
        SET proposal_id = 'legacy:evidence_annotation:' || id::text,
            source_excerpt = text,
            source_locator = '{"kind":"legacy","precision":"unavailable"}'::json,
            provenance = 'legacy_default',
            annotation_type = REPLACE(annotation_type, ' ', '_')
        """
    )
    with op.batch_alter_table("evidence_annotations") as batch_op:
        batch_op.alter_column("proposal_id", nullable=False)
        batch_op.alter_column("source_excerpt", nullable=False)
        batch_op.alter_column("source_locator", nullable=False)
        batch_op.alter_column("provenance", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("evidence_annotations") as batch_op:
        batch_op.drop_column("provenance")
        batch_op.drop_column("source_locator")
        batch_op.drop_column("source_excerpt")
        batch_op.drop_column("proposal_id")
