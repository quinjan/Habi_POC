"""create taxonomy decisions

Revision ID: 20260627_0005
Revises: 20260627_0004
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260627_0005"
down_revision: str | None = "20260627_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "taxonomy_nodes",
        sa.Column("normalized_name", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE taxonomy_nodes
        SET normalized_name = lower(regexp_replace(btrim(name), '\\s+', ' ', 'g'))
        """
    )
    op.alter_column("taxonomy_nodes", "normalized_name", nullable=False)
    op.create_index(
        "uq_taxonomy_nodes_root_normalized_name",
        "taxonomy_nodes",
        ["project_workspace_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index(
        "uq_taxonomy_nodes_child_normalized_name",
        "taxonomy_nodes",
        ["project_workspace_id", "parent_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )

    op.create_table(
        "taxonomy_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_workspace_id", sa.Integer(), nullable=False),
        sa.Column("review_batch_id", sa.Integer(), nullable=False),
        sa.Column("suggested_top_level_category", sa.String(length=255), nullable=False),
        sa.Column("suggested_subcategory", sa.String(length=255), nullable=True),
        sa.Column("normalized_suggested_path_key", sa.String(length=511), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("resolved_taxonomy_node_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["project_workspace_id"], ["project_workspaces.id"]),
        sa.ForeignKeyConstraint(["resolved_taxonomy_node_id"], ["taxonomy_nodes.id"]),
        sa.ForeignKeyConstraint(["review_batch_id"], ["review_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_taxonomy_decisions_project_workspace_id",
        "taxonomy_decisions",
        ["project_workspace_id"],
    )
    op.create_index(
        "ix_taxonomy_decisions_review_batch_id",
        "taxonomy_decisions",
        ["review_batch_id"],
    )
    op.create_index(
        "ix_taxonomy_decisions_normalized_suggested_path_key",
        "taxonomy_decisions",
        ["normalized_suggested_path_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_taxonomy_decisions_normalized_suggested_path_key",
        table_name="taxonomy_decisions",
    )
    op.drop_index("ix_taxonomy_decisions_review_batch_id", table_name="taxonomy_decisions")
    op.drop_index(
        "ix_taxonomy_decisions_project_workspace_id",
        table_name="taxonomy_decisions",
    )
    op.drop_table("taxonomy_decisions")
    op.drop_index("uq_taxonomy_nodes_child_normalized_name", table_name="taxonomy_nodes")
    op.drop_index("uq_taxonomy_nodes_root_normalized_name", table_name="taxonomy_nodes")
    op.drop_column("taxonomy_nodes", "normalized_name")
