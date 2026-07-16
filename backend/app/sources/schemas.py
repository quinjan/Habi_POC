from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.evidence.annotation_policy import is_workflow_noise
from backend.app.processing.schemas import ProcessingJobRead
from backend.app.projects.schemas import EvidenceAnnotationRead


LineType = Literal["material", "service"]
ManualSourceEntryType = Literal["structured_row", "free_form_text"]
EvidenceAnnotationType = Literal[
    "delivery_terms",
    "payment_terms",
    "validity_terms",
    "warranty_terms",
    "availability_terms",
    "condition_or_exclusion",
    "general_qualifier",
]
EvidenceAnnotationTarget = Literal["purchase_line", "material", "service", "provider"]


class StructuredEvidenceAnnotationInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    annotation_type: EvidenceAnnotationType
    target: EvidenceAnnotationTarget

    @model_validator(mode="after")
    def require_nonblank_text(self) -> "StructuredEvidenceAnnotationInput":
        if self.text.strip() == "":
            raise ValueError("Annotation text must not be blank")
        if is_workflow_noise(self.text):
            raise ValueError("Workflow and status noise cannot be submitted as an annotation")
        return self


class StructuredManualSourcePayload(BaseModel):
    line_type: LineType
    name: str = Field(min_length=1, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    price: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    provider_name: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    remarks_or_terms: str | None = Field(default=None, max_length=2000)
    annotations: list[StructuredEvidenceAnnotationInput] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_annotation_targets(self) -> "StructuredManualSourcePayload":
        legacy_annotation_count = int(
            self.remarks_or_terms is not None and self.remarks_or_terms.strip() != ""
        )
        if len(self.annotations) + legacy_annotation_count > 20:
            raise ValueError(
                "Structured manual source entries allow at most 20 annotations "
                "including legacy remarks or terms"
            )
        available_targets = {"purchase_line", self.line_type}
        if self.provider_name is not None and self.provider_name.strip() != "":
            available_targets.add("provider")
        if any(annotation.target not in available_targets for annotation in self.annotations):
            raise ValueError("Annotation target must be present on the structured row")
        return self


class ManualSourceEntryCreate(BaseModel):
    entry_type: ManualSourceEntryType
    structured_payload: StructuredManualSourcePayload | None = None
    original_text: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_entry_content(self) -> "ManualSourceEntryCreate":
        if self.entry_type == "structured_row" and self.structured_payload is None:
            raise ValueError("Structured manual source entries require structured_payload")
        if self.entry_type == "free_form_text":
            if self.original_text is None or self.original_text.strip() == "":
                raise ValueError("Free-form manual source entries require non-empty original_text")
        return self


class SourceSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    submission_type: str
    submitted_at: datetime
    entered_by: dict | None


class ManualSourceEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    source_submission_id: int
    entry_type: str
    structured_payload: dict | None
    original_text: str | None


class SourceFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    source_submission_id: int
    original_filename: str
    byte_size: int
    declared_mime_type: str | None
    uploaded_at: datetime
    sha256_checksum: str
    storage_path: str


class SourceFileInspectionRead(BaseModel):
    id: int
    original_filename: str
    byte_size: int
    declared_mime_type: str | None
    uploaded_at: datetime
    sha256_checksum: str
    available: bool


class SourceSubmissionContentRead(BaseModel):
    kind: Literal["structured_manual", "free_form_text", "xlsx"]
    structured_payload: dict | None = None
    original_text: str | None = None
    source_file: SourceFileInspectionRead | None = None


class SourceReviewBatchLinkRead(BaseModel):
    id: int
    status: str
    href: str


class SourceLinkedRecordRead(BaseModel):
    memory_record_id: int
    record_type: str
    name: str
    category_path: str


class SourcePurchaseLineLinkRead(BaseModel):
    id: int
    status: str
    href: str
    linked_records: list[SourceLinkedRecordRead]


class SourceImportedEvidenceRead(BaseModel):
    id: int
    source_label: str
    locator: dict | None
    supporting_content: dict
    annotations: list[EvidenceAnnotationRead]
    purchase_lines: list[SourcePurchaseLineLinkRead]
    annotation_omitted_count: int = 0
    annotation_detected_count: int = 0


class SourceSubmissionDetail(BaseModel):
    id: int
    project_workspace_id: int
    submission_type: str
    submitted_at: datetime
    source: SourceSubmissionContentRead
    processing_job: ProcessingJobRead | None
    review_batch: SourceReviewBatchLinkRead | None
    imported_evidence: list[SourceImportedEvidenceRead]
    empty_state: str | None
