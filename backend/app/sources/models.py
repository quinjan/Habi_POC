from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class ManualSourceEntry(Base):
    __tablename__ = "manual_source_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    structured_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
