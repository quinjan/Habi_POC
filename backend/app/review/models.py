from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class ReviewBatch(Base):
    __tablename__ = "review_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    source_submission_id: Mapped[int] = mapped_column(
        ForeignKey("source_submissions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="review_pending")


class ExtractedCandidate(Base):
    __tablename__ = "extracted_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    review_batch_id: Mapped[int] = mapped_column(
        ForeignKey("review_batches.id"), nullable=False, index=True
    )
    source_submission_id: Mapped[int] = mapped_column(
        ForeignKey("source_submissions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_review")
    proposed_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    merged_into_candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("extracted_candidates.id"), nullable=True
    )
    reviewed_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DuplicateCandidateGroup(Base):
    __tablename__ = "duplicate_candidate_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_workspace_id: Mapped[int] = mapped_column(
        ForeignKey("project_workspaces.id"), nullable=False, index=True
    )
    review_batch_id: Mapped[int] = mapped_column(
        ForeignKey("review_batches.id"), nullable=False, index=True
    )


class DuplicateCandidateGroupMember(Base):
    __tablename__ = "duplicate_candidate_group_members"
    __table_args__ = (
        UniqueConstraint("duplicate_group_id", "candidate_id", name="uq_duplicate_group_candidate"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    duplicate_group_id: Mapped[int] = mapped_column(
        ForeignKey("duplicate_candidate_groups.id"), nullable=False, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("extracted_candidates.id"), nullable=False, index=True
    )
