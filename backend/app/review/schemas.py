from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.processing.schemas import ProcessingJobRead, SourceFileSummary
from backend.app.sources.schemas import ManualSourceEntryRead, SourceFileRead, SourceSubmissionRead


class ReviewBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    source_submission_id: int
    status: str


class ExtractedCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    review_batch_id: int
    source_submission_id: int
    status: str
    proposed_payload: dict
    decision: str | None
    merged_into_candidate_id: int | None
    reviewed_payload: dict | None
    source_file: SourceFileSummary | None = None
    taxonomy_gate: "TaxonomyGateRead | None" = None
    taxonomy_gates: list["CandidateTaxonomyGateRead"] = Field(default_factory=list)
    existing_memory_matches: list["ExistingMemoryMatchRead"] = Field(default_factory=list)
    taxonomy_default: "TaxonomyDefaultRead | None" = None


class ManualSourceEntrySubmission(BaseModel):
    source_submission: SourceSubmissionRead
    manual_source_entry: ManualSourceEntryRead
    processing_job: ProcessingJobRead
    review_batch: ReviewBatchRead | None
    candidates: list[ExtractedCandidateRead]


class ManualSourceEntryQueuedSubmission(BaseModel):
    source_submission: SourceSubmissionRead
    manual_source_entry: ManualSourceEntryRead
    processing_job: ProcessingJobRead


class SourceFileQueuedSubmission(BaseModel):
    source_submission: SourceSubmissionRead
    source_file: SourceFileRead
    processing_job: ProcessingJobRead


class ReviewedConceptPayload(BaseModel):
    concept_type: Literal["material", "service"]
    name: str | None = Field(default=None, max_length=255)
    top_level_category: str | None = Field(default=None, max_length=255)
    subcategory: str | None = Field(default=None, max_length=255)


class ReviewedPurchaseLinePayload(BaseModel):
    linked_concepts: list[ReviewedConceptPayload] = Field(default_factory=list, max_length=2)
    provider_state: Literal["external", "internal", "unknown"] | None = None
    provider_top_level_category: str | None = Field(default=None, max_length=255)
    provider_subcategory: str | None = Field(default=None, max_length=255)

    # Legacy single-concept fields remain accepted while old review batches are migrated.
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

    def concepts(self) -> list[ReviewedConceptPayload]:
        if self.linked_concepts:
            return self.linked_concepts
        if self.line_type is None:
            return []
        return [
            ReviewedConceptPayload(
                concept_type=self.line_type,
                name=self.name,
                top_level_category=self.top_level_category,
                subcategory=self.subcategory,
            )
        ]


class CandidateDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected", "merged"] | None
    reviewed_payload: ReviewedPurchaseLinePayload | None = None
    merged_into_candidate_id: int | None = None


class ReviewBatchDraftCandidate(BaseModel):
    candidate_id: int
    included: bool
    reviewed_payload: ReviewedPurchaseLinePayload | None = None


class ReviewBatchDraftSaveRequest(BaseModel):
    candidates: list[ReviewBatchDraftCandidate] = Field(min_length=1)


class TaxonomyDecisionCreate(BaseModel):
    decision: Literal["approved", "mapped", "rejected"]
    suggested_top_level_category: str = Field(min_length=1, max_length=255)
    suggested_subcategory: str | None = Field(default=None, max_length=255)
    resolved_taxonomy_node_id: int | None = None


class ReviewBatchTaxonomyMappingRequest(BaseModel):
    candidate_id: int
    top_level_category: str = Field(min_length=1, max_length=255)
    subcategory: str = Field(min_length=1, max_length=255)
    apply_to_similar: bool = False


class TaxonomyGateReviewerDraftSaveRequest(BaseModel):
    top_level_category: str = Field(min_length=1, max_length=255)
    subcategory: str = Field(min_length=1, max_length=255)
    apply_to_similar: bool = False


class TaxonomyGateSelectionRequest(BaseModel):
    selected_proposal: Literal["ai_suggestion", "reviewer_draft"]


class TaxonomyDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    review_batch_id: int
    suggested_top_level_category: str
    suggested_subcategory: str | None
    normalized_suggested_path_key: str
    decision: str
    resolved_taxonomy_node_id: int | None
    taxonomy_gate_id: int | None = None
    candidate_id: int | None = None
    subject_type: str | None = None
    subject_name: str | None = None
    accepted_source: str | None = None
    superseded: bool = False
    created_at: datetime
    superseded_at: datetime | None = None
    accepted_category_path: str | None = None


class TaxonomyGateRead(BaseModel):
    status: str
    reason: str | None = None
    suggested_category_path: str
    resolved_category_path: str | None = None
    decision: str | None = None
    taxonomy_decision_id: int | None = None
    prior_rejection: dict | None = None


class CandidateTaxonomyGateRead(TaxonomyGateRead):
    id: int
    active: bool
    subject_type: Literal["material", "service", "provider"]
    subject_name: str
    original_ai_category_path: str
    reviewer_draft_category_path: str | None = None
    selected_proposal: Literal["ai_suggestion", "reviewer_draft"]
    selected_category_path: str
    accepted_category_path: str | None = None
    accepted_source: Literal["ai_suggestion", "reviewer_draft"] | None = None
    decision_history: list[TaxonomyDecisionRead] = Field(default_factory=list)


class ExistingMemoryMatchRead(BaseModel):
    subject_type: Literal["material", "service", "provider"]
    subject_name: str
    category_path: str


class TaxonomyDefaultRead(BaseModel):
    resolved_category_path: str
    source: str
    provenance_text: str
    taxonomy_decision_id: int


class TaxonomyNodePathRead(BaseModel):
    id: int
    name: str
    parent_id: int | None
    path: str


class TaxonomyNodeListRead(BaseModel):
    items: list[TaxonomyNodePathRead]


class TaxonomyNodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class ReviewBatchDetail(BaseModel):
    review_batch: ReviewBatchRead
    candidates: list[ExtractedCandidateRead]
    duplicate_groups: list["DuplicateCandidateGroupRead"] = Field(default_factory=list)
    duplicate_conflicts: list[str] = Field(default_factory=list)
    taxonomy_decisions: list[TaxonomyDecisionRead] = Field(default_factory=list)


class TaxonomyGateReviewerDraftSaveResponse(BaseModel):
    review_batch: ReviewBatchDetail
    affected_count: int


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
