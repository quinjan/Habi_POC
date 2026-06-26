from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base
from backend.app.sources.models import utc_now


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    source_submission_id: Mapped[int] = mapped_column(
        ForeignKey("source_submissions.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    processor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    candidate_count: Mapped[int] = mapped_column(nullable=False, default=0)
    review_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("review_batches.id"), nullable=True
    )
