from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class TaxonomyNode(Base):
    __tablename__ = "taxonomy_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("taxonomy_nodes.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "name" in kwargs and "normalized_name" not in kwargs:
            self.normalized_name = normalize_taxonomy_name(kwargs["name"])


class TaxonomyDecision(Base):
    __tablename__ = "taxonomy_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    review_batch_id: Mapped[int] = mapped_column(
        ForeignKey("review_batches.id"), nullable=False, index=True
    )
    suggested_top_level_category: Mapped[str] = mapped_column(String(255), nullable=False)
    suggested_subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_suggested_path_key: Mapped[str] = mapped_column(String(511), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    resolved_taxonomy_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("taxonomy_nodes.id"), nullable=True
    )
    taxonomy_gate_id: Mapped[int | None] = mapped_column(
        ForeignKey("taxonomy_gates.id"), nullable=True, index=True
    )
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("extracted_candidates.id"), nullable=True, index=True
    )
    subject_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    accepted_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TaxonomyGate(Base):
    __tablename__ = "taxonomy_gates"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "subject_type",
            "normalized_subject_name",
            name="uq_taxonomy_gate_candidate_subject",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    review_batch_id: Mapped[int] = mapped_column(
        ForeignKey("review_batches.id"), nullable=False, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("extracted_candidates.id"), nullable=False, index=True
    )
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_top_level_category: Mapped[str] = mapped_column(String(255), nullable=False)
    original_subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_original_path_key: Mapped[str] = mapped_column(String(511), nullable=False)
    reviewer_draft_top_level_category: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    reviewer_draft_subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_proposal: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ai_suggestion"
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="needs_decision")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


def normalize_taxonomy_name(value: str) -> str:
    return " ".join(value.casefold().split())


Index(
    "uq_taxonomy_nodes_root_normalized_name",
    TaxonomyNode.project_workspace_id,
    TaxonomyNode.normalized_name,
    unique=True,
    postgresql_where=TaxonomyNode.parent_id.is_(None),
)
Index(
    "uq_taxonomy_nodes_child_normalized_name",
    TaxonomyNode.project_workspace_id,
    TaxonomyNode.parent_id,
    TaxonomyNode.normalized_name,
    unique=True,
    postgresql_where=TaxonomyNode.parent_id.is_not(None),
)
