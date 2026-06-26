from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceSubmission(Base):
    __tablename__ = "source_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    submission_type: Mapped[str] = mapped_column(String(50), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    entered_by: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ManualSourceEntry(Base):
    __tablename__ = "manual_source_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    source_submission_id: Mapped[int] = mapped_column(
        ForeignKey("source_submissions.id"), nullable=False, unique=True
    )
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    structured_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
