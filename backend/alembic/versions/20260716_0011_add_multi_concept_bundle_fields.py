"""add multi-concept bundle fields and installation relationships

Revision ID: 20260716_0011
Revises: 20260716_0010
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_0011"
down_revision: str | None = "20260716_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("taxonomy_gates") as batch_op:
        batch_op.drop_constraint(
            "uq_taxonomy_gate_candidate_subject_type", type_="unique"
        )
        batch_op.create_unique_constraint(
            "uq_taxonomy_gate_candidate_subject",
            ["candidate_id", "subject_type", "normalized_subject_name"],
        )

    with op.batch_alter_table("purchase_line_concept_links") as batch_op:
        batch_op.drop_constraint("uq_purchase_line_concept_type", type_="unique")
        batch_op.add_column(sa.Column("concept_key", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("quantity", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("unit", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("component_unit_price", sa.String(length=100), nullable=True)
        )

    op.create_table(
        "purchase_line_installation_relationships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("purchase_line_id", sa.Integer(), nullable=False),
        sa.Column("service_concept_link_id", sa.Integer(), nullable=False),
        sa.Column("material_concept_link_id", sa.Integer(), nullable=False),
        sa.Column("source_excerpt", sa.String(length=2000), nullable=False),
        sa.Column("source_locator", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_line_id"], ["purchase_lines.id"]),
        sa.ForeignKeyConstraint(
            ["service_concept_link_id"], ["purchase_line_concept_links.id"]
        ),
        sa.ForeignKeyConstraint(
            ["material_concept_link_id"], ["purchase_line_concept_links.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_concept_link_id",
            "material_concept_link_id",
            name="uq_purchase_line_installation_pair",
        ),
    )
    op.create_index(
        "ix_purchase_line_installation_relationships_purchase_line_id",
        "purchase_line_installation_relationships",
        ["purchase_line_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_line_installation_relationships_purchase_line_id",
        table_name="purchase_line_installation_relationships",
    )
    op.drop_table("purchase_line_installation_relationships")
    with op.batch_alter_table("purchase_line_concept_links") as batch_op:
        batch_op.drop_column("component_unit_price")
        batch_op.drop_column("unit")
        batch_op.drop_column("quantity")
        batch_op.drop_column("concept_key")
        batch_op.create_unique_constraint(
            "uq_purchase_line_concept_type", ["purchase_line_id", "concept_type"]
        )
    with op.batch_alter_table("taxonomy_gates") as batch_op:
        batch_op.drop_constraint("uq_taxonomy_gate_candidate_subject", type_="unique")
        batch_op.create_unique_constraint(
            "uq_taxonomy_gate_candidate_subject_type",
            ["candidate_id", "subject_type"],
        )
