from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    manual_source_entry_id: Mapped[int] = mapped_column(
        ForeignKey("manual_source_entries.id"), nullable=False
    )
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)


class MemoryRecordEvidenceLink(Base):
    __tablename__ = "memory_record_evidence_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    memory_record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.id"), nullable=False)
    evidence_record_id: Mapped[int] = mapped_column(ForeignKey("evidence_records.id"), nullable=False)


class EvidenceAnnotation(Base):
    __tablename__ = "evidence_annotations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evidence_record_id: Mapped[int] = mapped_column(ForeignKey("evidence_records.id"), nullable=False)
    memory_record_id: Mapped[int] = mapped_column(ForeignKey("memory_records.id"), nullable=False)
    annotation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
