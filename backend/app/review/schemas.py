from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.sources.schemas import EvidenceAnnotationTarget, EvidenceAnnotationType

from backend.app.processing.schemas import ProcessingJobRead, SourceFileSummary
from backend.app.sources.schemas import ManualSourceEntryRead, SourceFileRead, SourceSubmissionRead


class ReviewBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    source_submission_id: int
    status: str


class AnnotationGroundingOptionRead(BaseModel):
    source_excerpt: str
    source_locator: dict


class CandidateSourceGroundingRead(BaseModel):
    kind: Literal["structured_manual", "free_form_text", "xlsx"]
    original_text: str | None = None
    options: list[AnnotationGroundingOptionRead] = Field(default_factory=list)


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
    source_grounding: CandidateSourceGroundingRead | None = None
    taxonomy_gate: "TaxonomyGateRead | None" = None
    taxonomy_gates: list["CandidateTaxonomyGateRead"] = Field(default_factory=list)
    existing_memory_matches: list["ExistingMemoryMatchRead"] = Field(default_factory=list)
    memory_options: list["MemoryOptionRead"] = Field(default_factory=list)
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
    model_config = ConfigDict(extra="forbid")

    concept_id: str | None = Field(default=None, max_length=100)
    concept_type: Literal["material", "service"]
    name: str | None = Field(default=None, max_length=255)
    observed_name_text: str | None = Field(default=None, max_length=2000)
    project_memory_record_id: int | None = None
    top_level_category: str | None = Field(default=None, max_length=255)
    subcategory: str | None = Field(default=None, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    component_unit_price: str | None = Field(default=None, max_length=100)


class ReviewedInstallationRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_concept_id: str = Field(min_length=1, max_length=100)
    material_concept_ids: list[str] = Field(min_length=1)
    source_excerpt: str = Field(min_length=1, max_length=2000)
    source_locator: dict


class ReviewedAnnotationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=2000)
    annotation_type: EvidenceAnnotationType
    target: EvidenceAnnotationTarget
    target_concept_id: str | None = Field(default=None, max_length=100)
    source_excerpt: str = Field(min_length=1, max_length=2000)
    source_locator: dict
    provenance: Literal[
        "source_field", "ai_suggested", "legacy_default", "reviewer_added"
    ]

    @model_validator(mode="after")
    def require_nonblank_content(self) -> "ReviewedAnnotationProposal":
        if self.text.strip() == "" or self.source_excerpt.strip() == "":
            raise ValueError("Annotation text and source excerpt must not be blank")
        if not self.source_locator:
            raise ValueError("Annotation source locator is required")
        return self


class ReviewedPurchaseLinePayload(BaseModel):
    linked_concepts: list[ReviewedConceptPayload] = Field(default_factory=list)
    provider_state: Literal["external", "internal", "unknown"] | None = None
    observed_provider_text: str | None = Field(default=None, max_length=2000)
    provider_memory_record_id: int | None = None
    provider_top_level_category: str | None = Field(default=None, max_length=255)
    provider_subcategory: str | None = Field(default=None, max_length=255)
    bundle_quantity: str | None = Field(default=None, max_length=100)
    bundle_unit: str | None = Field(default=None, max_length=100)
    installation_relationships: list[ReviewedInstallationRelationship] = Field(
        default_factory=list
    )
    primary_evidence_span: dict | None = None
    supporting_evidence_spans: list[dict] = Field(default_factory=list)

    # Legacy single-concept fields remain accepted while old review batches are migrated.
    line_type: Literal["material", "service"] | None = None
    name: str | None = Field(default=None, max_length=255)
    top_level_category: str | None = Field(default=None, max_length=255)
    subcategory: str | None = Field(default=None, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    price: str | None = Field(default=None, max_length=100)
    price_state: Literal["source_stated", "calculated", "defaulted", "unknown"] | None = None
    calculation: dict | None = None
    variance_warning: dict | None = None
    currency: str | None = Field(default=None, max_length=10)
    provider_name: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    remarks_or_terms: str | None = Field(default=None, max_length=2000)
    annotation_proposals: list[ReviewedAnnotationProposal] = Field(
        default_factory=list,
    )

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

    @model_validator(mode="after")
    def validate_annotations(self) -> "ReviewedPurchaseLinePayload":
        if self.provider_state in {"internal", "unknown"}:
            if self.provider_name is not None or self.provider_memory_record_id is not None:
                raise ValueError(
                    "Internal and Unknown Provider States cannot include Provider identity"
                )
        if self.provider_state == "unknown" and self.observed_provider_text is not None:
            raise ValueError("Unknown Provider State cannot include Observed Provider Text")
        available_targets = {"purchase_line", *(item.concept_type for item in self.concepts())}
        if self.provider_state == "external" and self.provider_name:
            available_targets.add("provider")
        duplicate_keys: set[tuple[str, str, str, str, str]] = set()
        for annotation in self.annotation_proposals:
            if annotation.target not in available_targets:
                raise ValueError("Annotation target must be present on the reviewed candidate")
            if annotation.target in {"material", "service"}:
                matching_concepts = [
                    concept
                    for concept in self.concepts()
                    if concept.concept_type == annotation.target
                ]
                if annotation.target_concept_id is not None:
                    if not any(
                        concept.concept_id == annotation.target_concept_id
                        for concept in matching_concepts
                    ):
                        raise ValueError("Annotation concept target is not present")
                elif len(matching_concepts) > 1:
                    raise ValueError(
                        "Repeated concept annotations require a target concept ID"
                    )
            elif annotation.target_concept_id is not None:
                raise ValueError(
                    "Purchase Line and Provider annotations cannot target a concept ID"
                )
            locator_key = repr(sorted(annotation.source_locator.items()))
            duplicate_key = (
                " ".join(annotation.text.casefold().split()),
                annotation.annotation_type,
                annotation.target,
                annotation.target_concept_id or "",
                locator_key,
            )
            if duplicate_key in duplicate_keys:
                raise ValueError("Exact duplicate annotations are not allowed")
            duplicate_keys.add(duplicate_key)

        concept_ids = [
            concept.concept_id for concept in self.linked_concepts if concept.concept_id
        ]
        if concept_ids and len(concept_ids) != len(self.linked_concepts):
            raise ValueError("Every repeated linked concept requires a concept ID")
        if len(concept_ids) != len(set(concept_ids)):
            raise ValueError("Linked concept IDs must be distinct")
        concepts_by_id = {
            concept.concept_id: concept for concept in self.linked_concepts if concept.concept_id
        }
        for relationship in self.installation_relationships:
            service = concepts_by_id.get(relationship.service_concept_id)
            if service is None or service.concept_type != "service":
                raise ValueError("Installation Relationship requires a linked Service")
            for material_id in relationship.material_concept_ids:
                material = concepts_by_id.get(material_id)
                if material is None or material.concept_type != "material":
                    raise ValueError("Installation Relationship requires linked Materials")
        return self


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


class MemoryOptionRead(BaseModel):
    record_id: int
    subject_type: Literal["material", "service", "provider"]
    subject_name: str
    category_path: str
    provider_roles: list[str] = Field(default_factory=list)


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
