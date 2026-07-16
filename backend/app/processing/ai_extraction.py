from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


CurrencyState = Literal["source_stated", "defaulted", "unknown"]
LineType = Literal["material", "service"]
ProviderState = Literal["external", "internal", "unknown"]
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


class AiAnnotationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    annotation_type: EvidenceAnnotationType
    target: EvidenceAnnotationTarget
    source_excerpt: str = Field(min_length=1, max_length=2000)

    @field_validator("text", "source_excerpt", mode="before")
    @classmethod
    def strip_annotation_text(cls, value: object) -> object:
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
    # Entries are validated independently so a malformed AI annotation never drops
    # an otherwise valid Purchase Line candidate.
    annotation_proposals: list[dict] = Field(default_factory=list)

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


def ground_free_form_annotation_proposals(
    payload: dict,
    *,
    original_text: str,
) -> tuple[dict, int, dict[str, int]]:
    raw_proposals = payload.get("annotation_proposals", [])
    grounded: list[dict] = []
    dropped_reasons: dict[str, int] = {}
    seen: set[tuple[str, str, str, int, int]] = set()

    for raw_proposal in raw_proposals:
        try:
            proposal = AiAnnotationProposal.model_validate(raw_proposal)
        except ValidationError:
            _count_reason(dropped_reasons, "invalid_shape")
            continue
        if _is_workflow_noise(proposal.text) or _is_workflow_noise(
            proposal.source_excerpt
        ):
            _count_reason(dropped_reasons, "workflow_noise")
            continue
        if not _annotation_target_available(payload, proposal.target):
            _count_reason(dropped_reasons, "target_unavailable")
            continue
        start = original_text.find(proposal.source_excerpt)
        if start < 0:
            _count_reason(dropped_reasons, "source_excerpt_not_found")
            continue
        end = start + len(proposal.source_excerpt)
        duplicate_key = (
            " ".join(proposal.text.casefold().split()),
            proposal.annotation_type,
            proposal.target,
            start,
            end,
        )
        if duplicate_key in seen:
            _count_reason(dropped_reasons, "exact_duplicate")
            continue
        seen.add(duplicate_key)
        if len(grounded) >= 20:
            _count_reason(dropped_reasons, "annotation_limit")
            continue
        grounded.append(
            {
                "proposal_id": f"ai:annotation:{len(grounded)}",
                "text": proposal.text,
                "annotation_type": proposal.annotation_type,
                "target": proposal.target,
                "source_excerpt": proposal.source_excerpt,
                "source_locator": {
                    "kind": "text_span",
                    "start": start,
                    "end": end,
                },
                "provenance": "ai_suggested",
            }
        )

    result = {**payload, "annotation_proposals": grounded}
    omitted_count = dropped_reasons.get("annotation_limit", 0)
    if omitted_count:
        result["annotation_omitted_count"] = omitted_count
        result["annotation_detected_count"] = len(grounded) + omitted_count
    return result, sum(dropped_reasons.values()), dropped_reasons


def _is_workflow_noise(value: str) -> bool:
    normalized = " ".join(value.casefold().strip(" .!?:;-").split())
    noise_phrases = {
        "paid",
        "paid already",
        "already paid",
        "for approval",
        "pending approval",
        "approved",
        "rejected",
        "call tomorrow",
        "follow up",
        "follow up tomorrow",
        "follow-up",
        "follow-up tomorrow",
    }
    return normalized in noise_phrases


def _annotation_target_available(payload: dict, target: str) -> bool:
    if target == "purchase_line":
        return True
    if target == "provider":
        return payload.get("provider_state") == "external" and bool(payload.get("provider_name"))
    linked_concepts = payload.get("linked_concepts")
    if isinstance(linked_concepts, list) and linked_concepts:
        return any(
            isinstance(concept, dict) and concept.get("concept_type") == target
            for concept in linked_concepts
        )
    return payload.get("line_type") == target


def _count_reason(reasons: dict[str, int], reason: str) -> None:
    reasons[reason] = reasons.get(reason, 0) + 1


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
