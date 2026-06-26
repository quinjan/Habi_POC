"""add source submissions and processing jobs

Revision ID: 20260627_0004
Revises: 20260626_0003
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260627_0004"
down_revision: str | None = "20260626_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("submission_type", sa.String(length=50), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("entered_by", sa.JSON(), nullable=True),
        sa.Column("legacy_manual_source_entry_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_submissions_project_workspace_id",
        "source_submissions",
        ["project_workspace_id"],
    )

    op.add_column(
        "manual_source_entries",
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "manual_source_entries",
        sa.Column(
            "entry_type",
            sa.String(length=50),
            nullable=True,
            server_default="structured_row",
        ),
    )
    op.add_column("manual_source_entries", sa.Column("original_text", sa.Text(), nullable=True))
    op.alter_column("manual_source_entries", "structured_payload", nullable=True)

    op.execute(
        """
        INSERT INTO source_submissions (
            project_workspace_id,
            submission_type,
            submitted_at,
            entered_by,
            legacy_manual_source_entry_id
        )
        SELECT
            project_workspace_id,
            'manual_source_entry',
            CURRENT_TIMESTAMP,
            NULL,
            id
        FROM manual_source_entries
        ORDER BY id
        """
    )
    op.execute(
        """
        UPDATE manual_source_entries AS manual_entry
        SET source_submission_id = source_submission.id
        FROM source_submissions AS source_submission
        WHERE source_submission.legacy_manual_source_entry_id = manual_entry.id
        """
    )

    with op.batch_alter_table("manual_source_entries") as batch_op:
        batch_op.alter_column("source_submission_id", nullable=False)
        batch_op.alter_column("entry_type", nullable=False, server_default=None)
        batch_op.create_foreign_key(
            "fk_manual_source_entries_source_submission_id",
            "source_submissions",
            ["source_submission_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_manual_source_entries_source_submission_id",
            ["source_submission_id"],
        )

    op.add_column(
        "review_batches",
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE review_batches AS review_batch
        SET source_submission_id = manual_entry.source_submission_id
        FROM manual_source_entries AS manual_entry
        WHERE manual_entry.id = review_batch.manual_source_entry_id
        """
    )
    with op.batch_alter_table("review_batches") as batch_op:
        batch_op.alter_column("source_submission_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_review_batches_source_submission_id",
            "source_submissions",
            ["source_submission_id"],
            ["id"],
        )
        batch_op.drop_constraint(
            "review_batches_manual_source_entry_id_fkey",
            type_="foreignkey",
        )
        batch_op.drop_column("manual_source_entry_id")

    op.add_column(
        "extracted_candidates",
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE extracted_candidates AS candidate
        SET source_submission_id = manual_entry.source_submission_id
        FROM manual_source_entries AS manual_entry
        WHERE manual_entry.id = candidate.manual_source_entry_id
        """
    )
    with op.batch_alter_table("extracted_candidates") as batch_op:
        batch_op.alter_column("source_submission_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_extracted_candidates_source_submission_id",
            "source_submissions",
            ["source_submission_id"],
            ["id"],
        )
        batch_op.drop_constraint(
            "extracted_candidates_manual_source_entry_id_fkey",
            type_="foreignkey",
        )
        batch_op.drop_column("manual_source_entry_id")

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("source_submission_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("processor_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_batch_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["review_batch_id"], ["review_batches.id"]),
        sa.ForeignKeyConstraint(["source_submission_id"], ["source_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_submission_id"),
    )
    op.create_index(
        "ix_processing_jobs_project_workspace_id",
        "processing_jobs",
        ["project_workspace_id"],
    )

    op.execute(
        """
        INSERT INTO processing_jobs (
            project_workspace_id,
            source_submission_id,
            status,
            source_type,
            processor_name,
            created_at,
            started_at,
            finished_at,
            candidate_count,
            review_batch_id
        )
        SELECT
            review_batch.project_workspace_id,
            review_batch.source_submission_id,
            'review_ready',
            'manual_source_entry',
            'structured_manual_row_v1',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            COUNT(candidate.id),
            review_batch.id
        FROM review_batches AS review_batch
        LEFT JOIN extracted_candidates AS candidate
            ON candidate.review_batch_id = review_batch.id
        GROUP BY review_batch.id, review_batch.project_workspace_id, review_batch.source_submission_id
        """
    )

    op.drop_column("source_submissions", "legacy_manual_source_entry_id")


def downgrade() -> None:
    op.add_column(
        "review_batches",
        sa.Column("manual_source_entry_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE review_batches AS review_batch
        SET manual_source_entry_id = manual_entry.id
        FROM manual_source_entries AS manual_entry
        WHERE manual_entry.source_submission_id = review_batch.source_submission_id
        """
    )
    with op.batch_alter_table("review_batches") as batch_op:
        batch_op.alter_column("manual_source_entry_id", nullable=False)
        batch_op.create_foreign_key(
            "review_batches_manual_source_entry_id_fkey",
            "manual_source_entries",
            ["manual_source_entry_id"],
            ["id"],
        )
        batch_op.drop_constraint("fk_review_batches_source_submission_id", type_="foreignkey")
        batch_op.drop_column("source_submission_id")

    op.add_column(
        "extracted_candidates",
        sa.Column("manual_source_entry_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE extracted_candidates AS candidate
        SET manual_source_entry_id = manual_entry.id
        FROM manual_source_entries AS manual_entry
        WHERE manual_entry.source_submission_id = candidate.source_submission_id
        """
    )
    with op.batch_alter_table("extracted_candidates") as batch_op:
        batch_op.alter_column("manual_source_entry_id", nullable=False)
        batch_op.create_foreign_key(
            "extracted_candidates_manual_source_entry_id_fkey",
            "manual_source_entries",
            ["manual_source_entry_id"],
            ["id"],
        )
        batch_op.drop_constraint(
            "fk_extracted_candidates_source_submission_id",
            type_="foreignkey",
        )
        batch_op.drop_column("source_submission_id")

    op.drop_index("ix_processing_jobs_project_workspace_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")

    with op.batch_alter_table("manual_source_entries") as batch_op:
        batch_op.drop_constraint(
            "uq_manual_source_entries_source_submission_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_manual_source_entries_source_submission_id",
            type_="foreignkey",
        )
        batch_op.drop_column("original_text")
        batch_op.drop_column("entry_type")
        batch_op.drop_column("source_submission_id")
        batch_op.alter_column("structured_payload", nullable=False)

    op.drop_index("ix_source_submissions_project_workspace_id", table_name="source_submissions")
    op.drop_table("source_submissions")
