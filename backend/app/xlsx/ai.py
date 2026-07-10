from datetime import date
from typing import Literal

from openpyxl.utils import column_index_from_string
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from backend.app.processing.ai_extraction import AiCategorySuggestion, CurrencyState, LineType


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

    line_type: LineType
    name: str = Field(min_length=1, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    price: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    currency_state: CurrencyState = "unknown"
    provider_name: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    remarks_or_terms: str | None = Field(default=None, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    category_suggestion: AiCategorySuggestion
    evidence: XlsxCandidateEvidence

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
        try:
            candidate = XlsxPurchaseLineCandidate.model_validate(raw_candidate)
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
        valid.append(candidate.model_dump(mode="json"))
    return valid, dropped


def _require_artifact_rows(
    row_numbers: list[int], artifact_rows: set[int], label: str
) -> None:
    if len(row_numbers) != len(set(row_numbers)):
        raise ValueError(f"Worksheet profile {label} rows must be distinct")
    if not set(row_numbers).issubset(artifact_rows):
        raise ValueError(f"Worksheet profile {label} row does not exist in the artifact")
