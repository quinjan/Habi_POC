from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.sources.schemas import ManualSourceEntryRead


class ReviewBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    manual_source_entry_id: int
    status: str


class ExtractedCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    review_batch_id: int
    manual_source_entry_id: int
    status: str
    proposed_payload: dict
    decision: str | None
    merged_into_candidate_id: int | None
    reviewed_payload: dict | None


class ManualSourceEntrySubmission(BaseModel):
    manual_source_entry: ManualSourceEntryRead
    review_batch: ReviewBatchRead
    candidate: ExtractedCandidateRead


class ReviewedPurchaseLinePayload(BaseModel):
    line_type: Literal["material", "service"] | None = None
    name: str | None = Field(default=None, max_length=255)
    top_level_category: str | None = Field(default=None, max_length=255)
    subcategory: str | None = Field(default=None, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    price: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    provider_name: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    remarks_or_terms: str | None = Field(default=None, max_length=2000)


class CandidateDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected", "merged"] | None
    reviewed_payload: ReviewedPurchaseLinePayload | None = None
    merged_into_candidate_id: int | None = None


class ReviewBatchDetail(BaseModel):
    review_batch: ReviewBatchRead
    candidates: list[ExtractedCandidateRead]
    duplicate_groups: list["DuplicateCandidateGroupRead"] = Field(default_factory=list)
    duplicate_conflicts: list[str] = Field(default_factory=list)


class DuplicateCandidateGroupCreate(BaseModel):
    member_candidate_ids: list[int] = Field(min_length=2)


class DuplicateCandidateGroupMembersRequest(BaseModel):
    add_candidate_ids: list[int] = Field(default_factory=list)
    remove_candidate_ids: list[int] = Field(default_factory=list)


class DuplicateCandidateGroupRead(BaseModel):
    id: int
    project_workspace_id: int
    review_batch_id: int
    member_candidate_ids: list[int]


class ImportedPurchaseLine(BaseModel):
    id: int


class ImportReviewBatchResponse(BaseModel):
    imported_purchase_lines: list[ImportedPurchaseLine]
