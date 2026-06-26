"""add duplicate candidate groups

Revision ID: 20260626_0003
Revises: 20260626_0002
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260626_0003"
down_revision: str | None = "20260626_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("extracted_candidates") as batch_op:
        batch_op.add_column(
            sa.Column("merged_into_candidate_id", sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_extracted_candidates_merged_into_candidate_id",
            "extracted_candidates",
            ["merged_into_candidate_id"],
            ["id"],
        )

    op.create_table(
        "duplicate_candidate_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("review_batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["review_batch_id"], ["review_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_duplicate_candidate_groups_project_workspace_id",
        "duplicate_candidate_groups",
        ["project_workspace_id"],
    )
    op.create_index(
        "ix_duplicate_candidate_groups_review_batch_id",
        "duplicate_candidate_groups",
        ["review_batch_id"],
    )

    op.create_table(
        "duplicate_candidate_group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("duplicate_group_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["extracted_candidates.id"]),
        sa.ForeignKeyConstraint(["duplicate_group_id"], ["duplicate_candidate_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "duplicate_group_id",
            "candidate_id",
            name="uq_duplicate_group_candidate",
        ),
    )
    op.create_index(
        "ix_duplicate_candidate_group_members_duplicate_group_id",
        "duplicate_candidate_group_members",
        ["duplicate_group_id"],
    )
    op.create_index(
        "ix_duplicate_candidate_group_members_candidate_id",
        "duplicate_candidate_group_members",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_duplicate_candidate_group_members_candidate_id",
        table_name="duplicate_candidate_group_members",
    )
    op.drop_index(
        "ix_duplicate_candidate_group_members_duplicate_group_id",
        table_name="duplicate_candidate_group_members",
    )
    op.drop_table("duplicate_candidate_group_members")
    op.drop_index(
        "ix_duplicate_candidate_groups_review_batch_id",
        table_name="duplicate_candidate_groups",
    )
    op.drop_index(
        "ix_duplicate_candidate_groups_project_workspace_id",
        table_name="duplicate_candidate_groups",
    )
    op.drop_table("duplicate_candidate_groups")
    with op.batch_alter_table("extracted_candidates") as batch_op:
        batch_op.drop_constraint(
            "fk_extracted_candidates_merged_into_candidate_id",
            type_="foreignkey",
        )
        batch_op.drop_column("merged_into_candidate_id")
