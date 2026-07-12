from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base
from backend.app.sources.models import utc_now


class WorksheetArtifact(Base):
    __tablename__ = "worksheet_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id", "worksheet_index", name="uq_worksheet_artifact_source_index"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    source_file_id: Mapped[int] = mapped_column(
        ForeignKey("source_files.id"), nullable=False, index=True
    )
    worksheet_index: Mapped[int] = mapped_column(nullable=False)
    worksheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    non_empty_row_count: Mapped[int] = mapped_column(nullable=False)
    non_empty_cell_count: Mapped[int] = mapped_column(nullable=False)
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
