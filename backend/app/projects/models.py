from datetime import date

from sqlalchemy import Date, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class ProjectWorkspace(Base):
    __tablename__ = "project_workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_year: Mapped[int | None] = mapped_column(nullable=True)
    floor_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trade_scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    client_or_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

