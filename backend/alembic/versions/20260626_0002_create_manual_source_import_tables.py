"""create manual source import tables

Revision ID: 20260626_0002
Revises: 20260626_0001
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260626_0002"
down_revision: str | None = "20260626_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "manual_source_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("structured_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_manual_source_entries_project_workspace_id",
        "manual_source_entries",
        ["project_workspace_id"],
    )

    op.create_table(
        "taxonomy_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["taxonomy_nodes.id"]),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_taxonomy_nodes_project_workspace_id",
        "taxonomy_nodes",
        ["project_workspace_id"],
    )

    op.create_table(
        "review_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("manual_source_entry_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["manual_source_entry_id"], ["manual_source_entries.id"]),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_batches_project_workspace_id",
        "review_batches",
        ["project_workspace_id"],
    )

    op.create_table(
        "memory_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("taxonomy_node_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["taxonomy_node_id"], ["taxonomy_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_records_project_workspace_id", "memory_records", ["project_workspace_id"])
    op.create_index("ix_memory_records_record_type", "memory_records", ["record_type"])
    op.create_index("ix_memory_records_normalized_name", "memory_records", ["normalized_name"])

    op.create_table(
        "extracted_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("review_batch_id", sa.Integer(), nullable=False),
        sa.Column("manual_source_entry_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("proposed_payload", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=True),
        sa.Column("reviewed_payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["manual_source_entry_id"], ["manual_source_entries.id"]),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["review_batch_id"], ["review_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extracted_candidates_project_workspace_id",
        "extracted_candidates",
        ["project_workspace_id"],
    )
    op.create_index(
        "ix_extracted_candidates_review_batch_id",
        "extracted_candidates",
        ["review_batch_id"],
    )

    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_record_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_record_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "providers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_record_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "purchase_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("memory_record_id", sa.Integer(), nullable=False),
        sa.Column("item_memory_record_id", sa.Integer(), nullable=False),
        sa.Column("provider_memory_record_id", sa.Integer(), nullable=True),
        sa.Column("item_or_service_name", sa.String(length=255), nullable=False),
        sa.Column("line_type", sa.String(length=50), nullable=False),
        sa.Column("provider_name", sa.String(length=255), nullable=True),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("provider_role", sa.String(length=50), nullable=True),
        sa.Column("quantity", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=100), nullable=True),
        sa.Column("unit_state", sa.String(length=50), nullable=False),
        sa.Column("price", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("price_state", sa.String(length=50), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("date_state", sa.String(length=50), nullable=False),
        sa.Column("category_path", sa.String(length=511), nullable=False),
        sa.ForeignKeyConstraint(["item_memory_record_id"], ["memory_records.id"]),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_records.id"]),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["provider_memory_record_id"], ["memory_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_lines_project_workspace_id", "purchase_lines", ["project_workspace_id"])

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("manual_source_entry_id", sa.Integer(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["manual_source_entry_id"], ["manual_source_entries.id"]),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_records_project_workspace_id", "evidence_records", ["project_workspace_id"])

    op.create_table(
        "memory_record_evidence_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_record_id", sa.Integer(), nullable=False),
        sa.Column("evidence_record_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["evidence_record_id"], ["evidence_records.id"]),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "evidence_annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_record_id", sa.Integer(), nullable=False),
        sa.Column("memory_record_id", sa.Integer(), nullable=False),
        sa.Column("annotation_type", sa.String(length=100), nullable=False),
        sa.Column("text", sa.String(length=2000), nullable=False),
        sa.ForeignKeyConstraint(["evidence_record_id"], ["evidence_records.id"]),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("evidence_annotations")
    op.drop_table("memory_record_evidence_links")
    op.drop_index("ix_evidence_records_project_workspace_id", table_name="evidence_records")
    op.drop_table("evidence_records")
    op.drop_index("ix_purchase_lines_project_workspace_id", table_name="purchase_lines")
    op.drop_table("purchase_lines")
    op.drop_table("providers")
    op.drop_table("services")
    op.drop_table("materials")
    op.drop_index("ix_extracted_candidates_review_batch_id", table_name="extracted_candidates")
    op.drop_index("ix_extracted_candidates_project_workspace_id", table_name="extracted_candidates")
    op.drop_table("extracted_candidates")
    op.drop_index("ix_memory_records_normalized_name", table_name="memory_records")
    op.drop_index("ix_memory_records_record_type", table_name="memory_records")
    op.drop_index("ix_memory_records_project_workspace_id", table_name="memory_records")
    op.drop_table("memory_records")
    op.drop_index("ix_review_batches_project_workspace_id", table_name="review_batches")
    op.drop_table("review_batches")
    op.drop_index("ix_taxonomy_nodes_project_workspace_id", table_name="taxonomy_nodes")
    op.drop_table("taxonomy_nodes")
    op.drop_index(
        "ix_manual_source_entries_project_workspace_id",
        table_name="manual_source_entries",
    )
    op.drop_table("manual_source_entries")
