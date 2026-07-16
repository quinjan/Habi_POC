from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    record_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    taxonomy_node_id: Mapped[int] = mapped_column(ForeignKey("taxonomy_nodes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.id"), nullable=False)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.id"), nullable=False)


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.id"), nullable=False)


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    memory_record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.id"), nullable=False)
    provider_memory_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("memory_records.id"), nullable=True
    )
    provider_state: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_state: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    price_state: Mapped[str] = mapped_column(String(50), nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_state: Mapped[str] = mapped_column(String(50), nullable=False)


class PurchaseLineConceptLink(Base):
    __tablename__ = "purchase_line_concept_links"
    __table_args__ = (
        UniqueConstraint(
            "purchase_line_id",
            "concept_type",
            name="uq_purchase_line_concept_type",
        ),
        UniqueConstraint(
            "purchase_line_id",
            "concept_memory_record_id",
            name="uq_purchase_line_concept_record",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    purchase_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_lines.id"), nullable=False, index=True
    )
    concept_memory_record_id: Mapped[int] = mapped_column(
        ForeignKey("memory_records.id"), nullable=False, index=True
    )
    concept_type: Mapped[str] = mapped_column(String(50), nullable=False)
