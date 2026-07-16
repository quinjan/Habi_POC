from datetime import date
from typing import Literal

from openpyxl.utils import column_index_from_string
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from backend.app.evidence.annotation_policy import is_workflow_noise

from backend.app.processing.ai_extraction import (
    AiAnnotationProposal,
    AiCategorySuggestion,
    AiLinkedConcept,
    CurrencyState,
    LineType,
    ProviderState,
)


class XlsxProfileRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_id: str = Field(min_length=1, max_length=100)
    usable: bool
    unusable_reason: str | None = Field(default=None, max_length=500)
    header_row_numbers: list[int] = Field(default_factory=list)
    body_start_row: int | None = Field(default=None, ge=1)
    body_end_row: int | None = Field(default=None, ge=1)
    columns: dict[str, str | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_usable_bounds_or_unusable_reason(self) -> "XlsxProfileRegion":
        if self.usable:
            if self.body_start_row is None or self.body_end_row is None:
                raise ValueError("Usable worksheet regions require body row bounds")
        elif not self.unusable_reason or not self.unusable_reason.strip():
            raise ValueError("Unusable worksheet regions require a reason")
        return self


class XlsxWorksheetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worksheet_name: str = Field(min_length=1, max_length=255)
    title_rows: list[int] = Field(default_factory=list)
    header_rows: list[int] = Field(default_factory=list)
    regions: list[XlsxProfileRegion] = Field(default_factory=list)


class XlsxEvidenceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=1)
    role: Literal["body", "context"]


class XlsxCandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_submission_id: int
    source_file_id: int
    worksheet: str
    region_id: str
    primary_body_row: int = Field(ge=1)
    locators: list[XlsxEvidenceLocator] = Field(min_length=1)


class XlsxPurchaseLineCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linked_concepts: list[AiLinkedConcept] = Field(default_factory=list, max_length=2)
    provider_state: ProviderState | None = None
    provider_category_suggestion: AiCategorySuggestion | None = None

    # Legacy XLSX providers remain valid while queued jobs migrate to linked concepts.
    line_type: LineType | None = None
    name: str | None = Field(default=None, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    price: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    currency_state: CurrencyState = "unknown"
    provider_name: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    remarks_or_terms: str | None = Field(default=None, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    category_suggestion: AiCategorySuggestion | None = None
    evidence: XlsxCandidateEvidence
    annotation_proposals: list[dict] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "quantity",
        "unit",
        "price",
        "currency",
        "provider_name",
        "remarks_or_terms",
        mode="before",
    )
    @classmethod
    def clean_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def default_currency_for_priced_candidate(self) -> "XlsxPurchaseLineCandidate":
        if self.price is not None and self.currency is None:
            self.currency = "PHP"
            self.currency_state = "defaulted"
        return self

    @model_validator(mode="after")
    def require_valid_concept_shape_and_provider(self) -> "XlsxPurchaseLineCandidate":
        if self.linked_concepts:
            concept_types = {concept.concept_type for concept in self.linked_concepts}
            if len(concept_types) != len(self.linked_concepts):
                raise ValueError("Linked concepts must have distinct types")
            if len(self.linked_concepts) == 2 and concept_types != {"material", "service"}:
                raise ValueError("Bundles require one Material and one Service")
        elif self.line_type is None or not self.name or self.category_suggestion is None:
            raise ValueError("Candidate requires linked concepts or one legacy concept")

        if self.provider_state == "external":
            if self.provider_name is None:
                raise ValueError("External Provider State requires a Provider name")
            if self.provider_category_suggestion is None:
                self.provider_category_suggestion = AiCategorySuggestion(
                    top_level_category="Providers",
                    subcategory="General",
                )
        elif self.provider_state == "unknown" and self.provider_name is not None:
            raise ValueError("Unknown Provider State cannot include a Provider name")
        return self


def validate_worksheet_profile(raw_profile: object, artifact: dict) -> dict:
    profile = XlsxWorksheetProfile.model_validate(raw_profile)
    worksheet_name = artifact["worksheet"]["name"]
    if profile.worksheet_name != worksheet_name:
        raise ValueError("Worksheet profile name does not match the artifact")

    artifact_rows = {cell["row"] for cell in artifact["cells"]}
    artifact_columns = {cell["column"] for cell in artifact["cells"]}
    _require_artifact_rows(profile.title_rows, artifact_rows, "title")
    _require_artifact_rows(profile.header_rows, artifact_rows, "header")

    region_ids: set[str] = set()
    for region in profile.regions:
        if region.region_id in region_ids:
            raise ValueError("Worksheet profile region IDs must be unique")
        region_ids.add(region.region_id)
        _require_artifact_rows(region.header_row_numbers, artifact_rows, "region header")
        if not region.usable:
            continue
        assert region.body_start_row is not None
        assert region.body_end_row is not None
        if region.body_start_row > region.body_end_row:
            raise ValueError("Worksheet profile body row bounds must be ordered")
        if not any(column is not None for column in region.columns.values()):
            raise ValueError("Usable worksheet regions require mapped columns")
        _require_artifact_rows(
            [region.body_start_row, region.body_end_row], artifact_rows, "body"
        )
        for column in region.columns.values():
            if column is None:
                continue
            try:
                column_index = column_index_from_string(column)
            except ValueError as error:
                raise ValueError("Worksheet profile column mapping is invalid") from error
            if column_index not in artifact_columns:
                raise ValueError("Worksheet profile column does not exist in the artifact")
    return profile.model_dump(mode="json")


def validate_xlsx_candidates(
    *,
    raw_candidates: list[object],
    source_submission_id: int,
    source_file_id: int,
    artifact: dict,
    profile: dict,
    expected_region_id: str,
    ground_ai_annotations: bool = True,
) -> tuple[list[dict], int]:
    valid: list[dict] = []
    dropped = 0
    region = next(
        (
            item
            for item in profile["regions"]
            if item["region_id"] == expected_region_id and item["usable"]
        ),
        None,
    )
    if region is None:
        return [], len(raw_candidates)

    artifact_rows = {cell["row"] for cell in artifact["cells"]}
    body_start = region["body_start_row"]
    body_end = region["body_end_row"]
    allowed_context_rows = set(
        profile["title_rows"] + profile["header_rows"] + region["header_row_numbers"]
    )
    for raw_candidate in raw_candidates:
        annotation_metadata: dict = {}
        candidate_input = raw_candidate
        if not ground_ai_annotations and isinstance(raw_candidate, dict):
            candidate_input = dict(raw_candidate)
            for field in (
                "dropped_annotation_count",
                "dropped_annotation_reasons",
                "annotation_omitted_count",
                "annotation_detected_count",
            ):
                if field in candidate_input:
                    annotation_metadata[field] = candidate_input.pop(field)
        try:
            candidate = XlsxPurchaseLineCandidate.model_validate(candidate_input)
        except ValidationError:
            dropped += 1
            continue
        evidence = candidate.evidence
        locator_rows = [locator.row for locator in evidence.locators]
        body_rows = [locator.row for locator in evidence.locators if locator.role == "body"]
        context_rows = [
            locator.row for locator in evidence.locators if locator.role == "context"
        ]
        if (
            evidence.source_submission_id != source_submission_id
            or evidence.source_file_id != source_file_id
            or evidence.worksheet != artifact["worksheet"]["name"]
            or evidence.region_id != expected_region_id
            or len(locator_rows) != len(set(locator_rows))
            or not set(locator_rows).issubset(artifact_rows)
            or not body_rows
            or any(row < body_start or row > body_end for row in body_rows)
            or not set(context_rows).issubset(allowed_context_rows)
            or evidence.primary_body_row not in body_rows
        ):
            dropped += 1
            continue
        payload = candidate.model_dump(mode="json")
        if ground_ai_annotations:
            payload.update(_ground_xlsx_annotations(candidate, artifact))
        else:
            payload.update(annotation_metadata)
        valid.append(payload)
    return valid, dropped


def _ground_xlsx_annotations(
    candidate: XlsxPurchaseLineCandidate,
    artifact: dict,
) -> dict:
    evidence_rows = {locator.row for locator in candidate.evidence.locators}
    cells = sorted(
        (
            cell
            for cell in artifact["cells"]
            if cell["row"] in evidence_rows
        ),
        key=lambda cell: (cell["row"], cell["column"]),
    )
    grounded: list[dict] = []
    dropped_reasons: dict[str, int] = {}
    seen: set[tuple[str, str, str, str]] = set()
    for raw_proposal in candidate.annotation_proposals:
        try:
            proposal = AiAnnotationProposal.model_validate(raw_proposal)
        except ValidationError:
            _count_annotation_drop(dropped_reasons, "invalid_shape")
            continue
        if is_workflow_noise(proposal.text) or is_workflow_noise(proposal.source_excerpt):
            _count_annotation_drop(dropped_reasons, "workflow_noise")
            continue
        if not _xlsx_annotation_target_available(candidate, proposal.target):
            _count_annotation_drop(dropped_reasons, "target_unavailable")
            continue
        source_cell = next(
            (
                cell
                for cell in cells
                if proposal.source_excerpt in str(cell.get("displayed_text") or "")
            ),
            None,
        )
        if source_cell is None:
            _count_annotation_drop(dropped_reasons, "source_excerpt_not_found")
            continue
        duplicate_key = (
            " ".join(proposal.text.casefold().split()),
            proposal.annotation_type,
            proposal.target,
            source_cell["coordinate"],
        )
        if duplicate_key in seen:
            _count_annotation_drop(dropped_reasons, "exact_duplicate")
            continue
        seen.add(duplicate_key)
        if len(grounded) >= 20:
            _count_annotation_drop(dropped_reasons, "annotation_limit")
            continue
        grounded.append(
            {
                "proposal_id": f"ai:xlsx:annotation:{len(grounded)}",
                "text": proposal.text,
                "annotation_type": proposal.annotation_type,
                "target": proposal.target,
                "source_excerpt": proposal.source_excerpt,
                "source_locator": {
                    "kind": "xlsx_cell",
                    "worksheet": candidate.evidence.worksheet,
                    "row": source_cell["row"],
                    "column": source_cell["column"],
                    "coordinate": source_cell["coordinate"],
                },
                "provenance": "ai_suggested",
            }
        )
    result = {"annotation_proposals": grounded}
    if dropped_reasons:
        result["dropped_annotation_count"] = sum(dropped_reasons.values())
        result["dropped_annotation_reasons"] = dropped_reasons
    omitted_count = dropped_reasons.get("annotation_limit", 0)
    if omitted_count:
        result["annotation_omitted_count"] = omitted_count
        result["annotation_detected_count"] = len(grounded) + omitted_count
    return result


def _xlsx_annotation_target_available(
    candidate: XlsxPurchaseLineCandidate,
    target: str,
) -> bool:
    if target == "purchase_line":
        return True
    if target == "provider":
        return candidate.provider_state == "external" and bool(candidate.provider_name)
    if candidate.linked_concepts:
        return any(concept.concept_type == target for concept in candidate.linked_concepts)
    return candidate.line_type == target


def _count_annotation_drop(reasons: dict[str, int], reason: str) -> None:
    reasons[reason] = reasons.get(reason, 0) + 1


def _require_artifact_rows(
    row_numbers: list[int], artifact_rows: set[int], label: str
) -> None:
    if len(row_numbers) != len(set(row_numbers)):
        raise ValueError(f"Worksheet profile {label} rows must be distinct")
    if not set(row_numbers).issubset(artifact_rows):
        raise ValueError(f"Worksheet profile {label} row does not exist in the artifact")
