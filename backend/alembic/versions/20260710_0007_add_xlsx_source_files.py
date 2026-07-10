"""add xlsx source files and worksheet artifacts

Revision ID: 20260710_0007
Revises: 20260627_0006
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_0007"
down_revision: str | None = "20260627_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("source_submission_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("declared_mime_type", sa.String(length=255), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256_checksum", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["source_submission_id"], ["source_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_submission_id"),
        sa.UniqueConstraint("storage_path"),
    )
    op.create_index(
        op.f("ix_source_files_project_workspace_id"),
        "source_files",
        ["project_workspace_id"],
        unique=False,
    )
    op.create_table(
        "worksheet_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("source_file_id", sa.Integer(), nullable=False),
        sa.Column("worksheet_index", sa.Integer(), nullable=False),
        sa.Column("worksheet_name", sa.String(length=255), nullable=False),
        sa.Column("artifact_path", sa.String(length=1000), nullable=False),
        sa.Column("non_empty_row_count", sa.Integer(), nullable=False),
        sa.Column("non_empty_cell_count", sa.Integer(), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_path"),
        sa.UniqueConstraint(
            "source_file_id",
            "worksheet_index",
            name="uq_worksheet_artifact_source_index",
        ),
    )
    op.create_index(
        op.f("ix_worksheet_artifacts_project_workspace_id"),
        "worksheet_artifacts",
        ["project_workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worksheet_artifacts_source_file_id"),
        "worksheet_artifacts",
        ["source_file_id"],
        unique=False,
    )
    op.add_column(
        "evidence_records", sa.Column("source_file_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_evidence_records_source_file_id_source_files",
        "evidence_records",
        "source_files",
        ["source_file_id"],
        ["id"],
    )
    op.alter_column(
        "evidence_records",
        "manual_source_entry_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_evidence_record_exactly_one_source",
        "evidence_records",
        "(manual_source_entry_id IS NOT NULL) <> (source_file_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_evidence_record_exactly_one_source", "evidence_records", type_="check"
    )
    op.execute(
        "DELETE FROM evidence_annotations WHERE evidence_record_id IN "
        "(SELECT id FROM evidence_records WHERE manual_source_entry_id IS NULL)"
    )
    op.execute(
        "DELETE FROM memory_record_evidence_links WHERE evidence_record_id IN "
        "(SELECT id FROM evidence_records WHERE manual_source_entry_id IS NULL)"
    )
    op.execute("DELETE FROM evidence_records WHERE manual_source_entry_id IS NULL")
    op.alter_column(
        "evidence_records",
        "manual_source_entry_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_constraint(
        "fk_evidence_records_source_file_id_source_files",
        "evidence_records",
        type_="foreignkey",
    )
    op.drop_column("evidence_records", "source_file_id")
    op.drop_index(
        op.f("ix_worksheet_artifacts_source_file_id"),
        table_name="worksheet_artifacts",
    )
    op.drop_index(
        op.f("ix_worksheet_artifacts_project_workspace_id"),
        table_name="worksheet_artifacts",
    )
    op.drop_table("worksheet_artifacts")
    op.drop_index(op.f("ix_source_files_project_workspace_id"), table_name="source_files")
    op.drop_table("source_files")
