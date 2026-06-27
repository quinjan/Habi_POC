from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


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
