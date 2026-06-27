from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


CurrencyState = Literal["source_stated", "defaulted", "unknown"]
LineType = Literal["material", "service"]


class AiExtractionProvider(Protocol):
    def extract_purchase_lines(
        self,
        *,
        original_text: str,
        source_submission_id: int,
    ) -> dict:
        """Return provider-specific AI extraction output."""


class AiCandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_submission_id: int
    locator: Literal["manual_source_entry.original_text"]


class AiCategorySuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_level_category: str = Field(min_length=1, max_length=255)
    subcategory: str = Field(min_length=1, max_length=255)

    @field_validator("top_level_category", "subcategory", mode="before")
    @classmethod
    def strip_required_taxonomy_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AiPurchaseLineCandidate(BaseModel):
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
    evidence: AiCandidateEvidence

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

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
    def clean_optional_string_fields(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value

    @model_validator(mode="after")
    def default_currency_for_priced_candidates(self) -> "AiPurchaseLineCandidate":
        if self.price is not None and self.price.strip() != "" and self.currency is None:
            self.currency = "PHP"
            self.currency_state = "defaulted"
        return self


def validate_ai_candidates(
    *,
    source_submission_id: int,
    raw_candidates: list[dict],
) -> tuple[list[dict], int]:
    valid: list[dict] = []
    dropped = 0
    for raw_candidate in raw_candidates:
        try:
            candidate = AiPurchaseLineCandidate.model_validate(raw_candidate)
        except ValidationError:
            dropped += 1
            continue
        if candidate.evidence.source_submission_id != source_submission_id:
            dropped += 1
            continue
        valid.append(candidate.model_dump(mode="json"))
    return valid, dropped
