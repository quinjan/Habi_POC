"""add candidate-scoped taxonomy gates

Revision ID: 20260715_0009
Revises: 20260713_0008
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260715_0009"
down_revision: str | None = "20260713_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_gates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("review_batch_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_subject_name", sa.String(length=255), nullable=False),
        sa.Column("original_top_level_category", sa.String(length=255), nullable=False),
        sa.Column("original_subcategory", sa.String(length=255), nullable=True),
        sa.Column("normalized_original_path_key", sa.String(length=511), nullable=False),
        sa.Column("reviewer_draft_top_level_category", sa.String(length=255), nullable=True),
        sa.Column("reviewer_draft_subcategory", sa.String(length=255), nullable=True),
        sa.Column(
            "selected_proposal",
            sa.String(length=50),
            nullable=False,
            server_default="ai_suggestion",
        ),
        sa.Column(
            "status", sa.String(length=50), nullable=False, server_default="needs_decision"
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["candidate_id"], ["extracted_candidates.id"]),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["review_batch_id"], ["review_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id", "subject_type", name="uq_taxonomy_gate_candidate_subject_type"
        ),
    )
    for column_name in ("project_workspace_id", "review_batch_id", "candidate_id"):
        op.create_index(
            op.f(f"ix_taxonomy_gates_{column_name}"), "taxonomy_gates", [column_name]
        )

    op.add_column("taxonomy_decisions", sa.Column("taxonomy_gate_id", sa.Integer(), nullable=True))
    op.add_column("taxonomy_decisions", sa.Column("candidate_id", sa.Integer(), nullable=True))
    op.add_column("taxonomy_decisions", sa.Column("subject_type", sa.String(length=50), nullable=True))
    op.add_column("taxonomy_decisions", sa.Column("subject_name", sa.String(length=255), nullable=True))
    op.add_column("taxonomy_decisions", sa.Column("accepted_source", sa.String(length=50), nullable=True))
    op.add_column(
        "taxonomy_decisions",
        sa.Column("superseded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "taxonomy_decisions", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "taxonomy_decisions_taxonomy_gate_id_fkey",
        "taxonomy_decisions",
        "taxonomy_gates",
        ["taxonomy_gate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "taxonomy_decisions_candidate_id_fkey",
        "taxonomy_decisions",
        "extracted_candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_taxonomy_decisions_taxonomy_gate_id"),
        "taxonomy_decisions",
        ["taxonomy_gate_id"],
    )
    op.create_index(
        op.f("ix_taxonomy_decisions_candidate_id"),
        "taxonomy_decisions",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_taxonomy_decisions_candidate_id"), table_name="taxonomy_decisions")
    op.drop_index(op.f("ix_taxonomy_decisions_taxonomy_gate_id"), table_name="taxonomy_decisions")
    op.drop_constraint(
        "taxonomy_decisions_candidate_id_fkey", "taxonomy_decisions", type_="foreignkey"
    )
    op.drop_constraint(
        "taxonomy_decisions_taxonomy_gate_id_fkey", "taxonomy_decisions", type_="foreignkey"
    )
    for column_name in (
        "superseded_at",
        "superseded",
        "accepted_source",
        "subject_name",
        "subject_type",
        "candidate_id",
        "taxonomy_gate_id",
    ):
        op.drop_column("taxonomy_decisions", column_name)
    for column_name in ("candidate_id", "review_batch_id", "project_workspace_id"):
        op.drop_index(op.f(f"ix_taxonomy_gates_{column_name}"), table_name="taxonomy_gates")
    op.drop_table("taxonomy_gates")
