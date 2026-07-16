"""add linked concepts, provider state, and contractor assigned

Revision ID: 20260713_0008
Revises: 20260710_0007
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_0008"
down_revision: str | None = "20260710_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_workspaces",
        sa.Column(
            "contractor_assigned",
            sa.String(length=255),
            nullable=False,
            server_default="Internal",
        ),
    )
    op.alter_column("project_workspaces", "contractor_assigned", server_default=None)

    op.create_table(
        "purchase_line_concept_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("purchase_line_id", sa.Integer(), nullable=False),
        sa.Column("concept_memory_record_id", sa.Integer(), nullable=False),
        sa.Column("concept_type", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["concept_memory_record_id"], ["memory_records.id"]),
        sa.ForeignKeyConstraint(["purchase_line_id"], ["purchase_lines.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "purchase_line_id",
            "concept_memory_record_id",
            name="uq_purchase_line_concept_record",
        ),
        sa.UniqueConstraint(
            "purchase_line_id",
            "concept_type",
            name="uq_purchase_line_concept_type",
        ),
    )
    op.create_index(
        op.f("ix_purchase_line_concept_links_purchase_line_id"),
        "purchase_line_concept_links",
        ["purchase_line_id"],
    )
    op.create_index(
        op.f("ix_purchase_line_concept_links_concept_memory_record_id"),
        "purchase_line_concept_links",
        ["concept_memory_record_id"],
    )
    op.execute(
        """
        INSERT INTO purchase_line_concept_links (
            purchase_line_id, concept_memory_record_id, concept_type
        )
        SELECT id, item_memory_record_id, line_type
        FROM purchase_lines
        WHERE line_type IN ('material', 'service')
        """
    )

    op.add_column(
        "purchase_lines",
        sa.Column(
            "provider_state",
            sa.String(length=50),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.execute(
        """
        UPDATE purchase_lines
        SET provider_state = CASE
            WHEN provider_type IN ('external', 'internal', 'unknown') THEN provider_type
            WHEN provider_memory_record_id IS NOT NULL THEN 'external'
            ELSE 'unknown'
        END
        """
    )
    op.alter_column("purchase_lines", "provider_state", server_default=None)

    op.execute(
        """
        INSERT INTO taxonomy_nodes (project_workspace_id, parent_id, name, normalized_name)
        SELECT DISTINCT provider.project_workspace_id, NULL::integer, 'Providers', 'providers'
        FROM memory_records AS provider
        WHERE provider.record_type = 'provider'
          AND NOT EXISTS (
              SELECT 1 FROM taxonomy_nodes AS existing
              WHERE existing.project_workspace_id = provider.project_workspace_id
                AND existing.parent_id IS NULL
                AND existing.normalized_name = 'providers'
          )
        """
    )
    op.execute(
        """
        INSERT INTO taxonomy_nodes (project_workspace_id, parent_id, name, normalized_name)
        SELECT roots.project_workspace_id, roots.id, 'General', 'general'
        FROM taxonomy_nodes AS roots
        WHERE roots.parent_id IS NULL
          AND roots.normalized_name = 'providers'
          AND EXISTS (
              SELECT 1 FROM memory_records AS provider
              WHERE provider.project_workspace_id = roots.project_workspace_id
                AND provider.record_type = 'provider'
          )
          AND NOT EXISTS (
              SELECT 1 FROM taxonomy_nodes AS existing
              WHERE existing.project_workspace_id = roots.project_workspace_id
                AND existing.parent_id = roots.id
                AND existing.normalized_name = 'general'
          )
        """
    )
    op.execute(
        """
        UPDATE memory_records AS provider
        SET taxonomy_node_id = general.id
        FROM taxonomy_nodes AS general
        JOIN taxonomy_nodes AS roots ON roots.id = general.parent_id
        WHERE provider.record_type = 'provider'
          AND provider.project_workspace_id = general.project_workspace_id
          AND roots.normalized_name = 'providers'
          AND general.normalized_name = 'general'
        """
    )

    with op.batch_alter_table("purchase_lines") as batch_op:
        batch_op.drop_constraint(
            "purchase_lines_item_memory_record_id_fkey",
            type_="foreignkey",
        )
        for column_name in (
            "item_memory_record_id",
            "item_or_service_name",
            "line_type",
            "provider_name",
            "provider_type",
            "provider_role",
            "category_path",
        ):
            batch_op.drop_column(column_name)


def downgrade() -> None:
    with op.batch_alter_table("purchase_lines") as batch_op:
        batch_op.add_column(sa.Column("category_path", sa.String(length=511), nullable=True))
        batch_op.add_column(sa.Column("provider_role", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("provider_type", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("provider_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("line_type", sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column("item_or_service_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("item_memory_record_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "purchase_lines_item_memory_record_id_fkey",
            "memory_records",
            ["item_memory_record_id"],
            ["id"],
        )

    op.execute(
        """
        UPDATE purchase_lines AS line
        SET item_memory_record_id = selected.concept_memory_record_id,
            line_type = selected.concept_type,
            item_or_service_name = concept.display_name,
            provider_name = provider.display_name,
            provider_type = line.provider_state,
            provider_role = CASE
                WHEN line.provider_state = 'unknown' THEN NULL
                WHEN selected.concept_type = 'material' THEN 'material_supplier'
                ELSE 'service_provider'
            END,
            category_path = parent.name || ' / ' || child.name
        FROM LATERAL (
            SELECT link.concept_memory_record_id, link.concept_type
            FROM purchase_line_concept_links AS link
            WHERE link.purchase_line_id = line.id
            ORDER BY CASE WHEN link.concept_type = 'material' THEN 0 ELSE 1 END
            LIMIT 1
        ) AS selected
        JOIN memory_records AS concept ON concept.id = selected.concept_memory_record_id
        JOIN taxonomy_nodes AS child ON child.id = concept.taxonomy_node_id
        JOIN taxonomy_nodes AS parent ON parent.id = child.parent_id
        LEFT JOIN memory_records AS provider ON provider.id = line.provider_memory_record_id
        """
    )
    with op.batch_alter_table("purchase_lines") as batch_op:
        batch_op.alter_column("item_memory_record_id", nullable=False)
        batch_op.alter_column("item_or_service_name", nullable=False)
        batch_op.alter_column("line_type", nullable=False)
        batch_op.alter_column("provider_type", nullable=False)
        batch_op.alter_column("category_path", nullable=False)
        batch_op.drop_column("provider_state")

    op.drop_index(
        op.f("ix_purchase_line_concept_links_concept_memory_record_id"),
        table_name="purchase_line_concept_links",
    )
    op.drop_index(
        op.f("ix_purchase_line_concept_links_purchase_line_id"),
        table_name="purchase_line_concept_links",
    )
    op.drop_table("purchase_line_concept_links")
    op.drop_column("project_workspaces", "contractor_assigned")
