from datetime import date

from sqlalchemy import Date, ForeignKey, String
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
    item_memory_record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.id"), nullable=False)
    provider_memory_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("memory_records.id"), nullable=True
    )
    item_or_service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    line_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_state: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    price_state: Mapped[str] = mapped_column(String(50), nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_state: Mapped[str] = mapped_column(String(50), nullable=False)
    category_path: Mapped[str] = mapped_column(String(511), nullable=False)
