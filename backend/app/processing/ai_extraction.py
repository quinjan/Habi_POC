from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


CurrencyState = Literal["source_stated", "defaulted", "unknown"]
LineType = Literal["material", "service"]
ProviderState = Literal["external", "internal", "unknown"]


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


class AiLinkedConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_type: LineType
    name: str = Field(min_length=1, max_length=255)
    category_suggestion: AiCategorySuggestion

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AiPurchaseLineCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linked_concepts: list[AiLinkedConcept] = Field(default_factory=list, max_length=2)
    provider_state: ProviderState | None = None
    provider_category_suggestion: AiCategorySuggestion | None = None

    # Legacy single-concept AI payloads remain valid for queued jobs and old providers.
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

    @model_validator(mode="after")
    def require_valid_concept_shape_and_provider(self) -> "AiPurchaseLineCandidate":
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


def apply_contractor_assigned_provider_default(
    payload: dict,
    *,
    contractor_assigned: str,
) -> dict:
    provider_name = payload.get("provider_name")
    normalized_contractor = _normalize(contractor_assigned)
    if (
        normalized_contractor != "internal"
        and isinstance(provider_name, str)
        and _normalize(provider_name) == normalized_contractor
    ):
        return {
            **payload,
            "provider_state": "internal",
            "provider_category_suggestion": None,
        }
    return payload


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
