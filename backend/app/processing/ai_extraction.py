from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from backend.app.evidence.annotation_policy import is_workflow_noise


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

    @model_validator(mode="after")
    def reject_malformed_taxonomy_fields(self) -> "AiCategorySuggestion":
        if "/" in self.top_level_category:
            raise ValueError("Top-Level Category cannot contain a slash")
        if self.subcategory.startswith("/"):
            raise ValueError("Subcategory cannot start with a slash")
        return self


class AiLinkedConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str | None = Field(default=None, min_length=1, max_length=100)
    concept_type: LineType
    name: str = Field(min_length=1, max_length=255)
    observed_name_text: str | None = Field(default=None, min_length=1, max_length=2000)
    project_memory_record_id: int | None = None
    category_suggestion: AiCategorySuggestion
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    component_unit_price: str | None = Field(default=None, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "observed_name_text", "quantity", "unit", "component_unit_price", mode="before"
    )
    @classmethod
    def clean_optional_concept_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value


class AiInstallationRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_concept_id: str = Field(min_length=1, max_length=100)
    material_concept_ids: list[str] = Field(min_length=1)
    source_excerpt: str = Field(min_length=1, max_length=2000)

    @field_validator("service_concept_id", "source_excerpt", mode="before")
    @classmethod
    def strip_required_relationship_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AiAnnotationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    annotation_type: EvidenceAnnotationType
    target: EvidenceAnnotationTarget
    target_concept_id: str | None = Field(default=None, max_length=100)
    source_excerpt: str = Field(min_length=1, max_length=2000)

    @field_validator("text", "source_excerpt", mode="before")
    @classmethod
    def strip_annotation_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AiPurchaseLineCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linked_concepts: list[AiLinkedConcept] = Field(default_factory=list)
    provider_state: ProviderState | None = None
    provider_category_suggestion: AiCategorySuggestion | None = None
    observed_provider_text: str | None = Field(default=None, max_length=2000)
    provider_memory_record_id: int | None = None
    bundle_quantity: str | None = Field(default=None, max_length=100)
    bundle_unit: str | None = Field(default=None, max_length=100)
    source_stated_line_total: str | None = Field(default=None, max_length=100)
    primary_evidence_excerpt: str | None = Field(default=None, max_length=12000)
    supporting_evidence_excerpts: list[str] = Field(default_factory=list)
    installation_relationships: list[AiInstallationRelationship] = Field(
        default_factory=list
    )

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
        "observed_provider_text",
        "bundle_quantity",
        "bundle_unit",
        "source_stated_line_total",
        "primary_evidence_excerpt",
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
            concept_ids = [
                concept.concept_id
                for concept in self.linked_concepts
                if concept.concept_id is not None
            ]
            if concept_ids and len(concept_ids) != len(self.linked_concepts):
                raise ValueError("Every linked concept must provide a concept ID")
            if len(concept_ids) != len(set(concept_ids)):
                raise ValueError("Linked concept IDs must be distinct")

            concepts_by_id = {
                concept.concept_id: concept
                for concept in self.linked_concepts
                if concept.concept_id is not None
            }
            for relationship in self.installation_relationships:
                service = concepts_by_id.get(relationship.service_concept_id)
                if service is None or service.concept_type != "service":
                    raise ValueError(
                        "Installation Relationship requires a linked Service"
                    )
                if len(relationship.material_concept_ids) != len(
                    set(relationship.material_concept_ids)
                ):
                    raise ValueError(
                        "Installation Relationship Material IDs must be distinct"
                    )
                for material_id in relationship.material_concept_ids:
                    material = concepts_by_id.get(material_id)
                    if material is None or material.concept_type != "material":
                        raise ValueError(
                            "Installation Relationship requires linked Materials"
                        )
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
        elif self.provider_state == "internal":
            if self.provider_memory_record_id is not None:
                raise ValueError("Internal Provider State cannot include a Memory match")
        elif self.provider_state == "unknown":
            if self.provider_name is not None or self.provider_memory_record_id is not None:
                raise ValueError("Unknown Provider State cannot include Provider details")
            if self.observed_provider_text is not None:
                raise ValueError("Unknown Provider State cannot include Observed Provider Text")
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


def validate_project_memory_matches(payload: dict, *, memory_context: dict) -> list[dict]:
    failures: list[dict] = []
    collections = {
        "material": memory_context.get("materials", []),
        "service": memory_context.get("services", []),
        "provider": memory_context.get("providers", []),
    }

    for concept in payload.get("linked_concepts", []):
        record_id = concept.get("project_memory_record_id")
        if record_id is None:
            continue
        concept_type = concept.get("concept_type")
        _validate_supplied_memory_match(
            failures,
            record_id=record_id,
            record_type=concept_type,
            proposed_name=concept.get("name"),
            proposed_category=concept.get("category_suggestion"),
            supplied_records=collections.get(concept_type, []),
        )

    provider_record_id = payload.get("provider_memory_record_id")
    if provider_record_id is not None:
        _validate_supplied_memory_match(
            failures,
            record_id=provider_record_id,
            record_type="provider",
            proposed_name=payload.get("provider_name"),
            proposed_category=payload.get("provider_category_suggestion"),
            supplied_records=collections["provider"],
        )
    return failures


def _validate_supplied_memory_match(
    failures: list[dict],
    *,
    record_id: int,
    record_type: str,
    proposed_name: object,
    proposed_category: object,
    supplied_records: list[dict],
) -> None:
    label = record_type.title()
    supplied_record = next(
        (record for record in supplied_records if record.get("record_id") == record_id),
        None,
    )
    if supplied_record is None:
        failures.append(
            {
                "reason": (
                    f"Proposed {label} Memory Record was not supplied from the selected "
                    "project"
                ),
                "reason_code": "project_memory_match_not_supplied",
                "record_id": record_id,
            }
        )
        return

    if proposed_name != supplied_record.get("name"):
        failures.append(
            {
                "reason": f"Proposed {label} name does not match the supplied Memory Record",
                "reason_code": "project_memory_match_name_mismatch",
                "record_id": record_id,
            }
        )
    category_path = None
    if isinstance(proposed_category, dict):
        category_path = (
            f"{proposed_category.get('top_level_category')} / "
            f"{proposed_category.get('subcategory')}"
        )
    if category_path != supplied_record.get("category_path"):
        failures.append(
            {
                "reason": (
                    f"Proposed {label} category does not match the supplied Memory Record"
                ),
                "reason_code": "project_memory_match_category_mismatch",
                "record_id": record_id,
            }
        )


def ground_free_form_annotation_proposals(
    payload: dict,
    *,
    original_text: str,
) -> tuple[dict, int, dict[str, int]]:
    raw_proposals = payload.get("annotation_proposals", [])
    grounded: list[dict] = []
    dropped_reasons: dict[str, int] = {}
    validation_failures: list[dict] = []
    seen: set[tuple[str, str, str, str, int, int]] = set()

    for raw_proposal in raw_proposals:
        try:
            proposal = AiAnnotationProposal.model_validate(raw_proposal)
        except ValidationError:
            _count_reason(dropped_reasons, "invalid_shape")
            validation_failures.append(
                _annotation_validation_failure(
                    raw_proposal, "invalid_shape", original_text=original_text
                )
            )
            continue
        if is_workflow_noise(proposal.text) or is_workflow_noise(
            proposal.source_excerpt
        ):
            _count_reason(dropped_reasons, "workflow_noise")
            validation_failures.append(
                _annotation_validation_failure(
                    raw_proposal, "workflow_noise", original_text=original_text
                )
            )
            continue
        if not _annotation_target_available(
            payload, proposal.target, proposal.target_concept_id
        ):
            _count_reason(dropped_reasons, "target_unavailable")
            validation_failures.append(
                _annotation_validation_failure(
                    raw_proposal, "target_unavailable", original_text=original_text
                )
            )
            continue
        candidate_excerpts = [
            payload.get("primary_evidence_excerpt"),
            *payload.get("supporting_evidence_excerpts", []),
        ]
        candidate_excerpts = [
            excerpt for excerpt in candidate_excerpts if isinstance(excerpt, str)
        ]
        if candidate_excerpts and not any(
            proposal.source_excerpt in excerpt for excerpt in candidate_excerpts
        ):
            _count_reason(dropped_reasons, "outside_candidate_spans")
            validation_failures.append(
                _annotation_validation_failure(
                    raw_proposal,
                    "outside_candidate_spans",
                    original_text=original_text,
                )
            )
            continue
        start = original_text.find(proposal.source_excerpt)
        if start < 0:
            _count_reason(dropped_reasons, "source_excerpt_not_found")
            validation_failures.append(
                _annotation_validation_failure(
                    raw_proposal,
                    "source_excerpt_not_found",
                    original_text=original_text,
                )
            )
            continue
        end = start + len(proposal.source_excerpt)
        duplicate_key = (
            " ".join(proposal.text.casefold().split()),
            proposal.annotation_type,
            proposal.target,
            proposal.target_concept_id or "",
            start,
            end,
        )
        if duplicate_key in seen:
            _count_reason(dropped_reasons, "exact_duplicate")
            continue
        seen.add(duplicate_key)
        grounded.append(
            {
                "proposal_id": f"ai:annotation:{len(grounded)}",
                "text": proposal.text,
                "annotation_type": proposal.annotation_type,
                "target": proposal.target,
                **(
                    {"target_concept_id": proposal.target_concept_id}
                    if proposal.target_concept_id is not None
                    else {}
                ),
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
    if validation_failures:
        result["annotation_validation_failures"] = validation_failures
    return result, sum(dropped_reasons.values()), dropped_reasons


def _annotation_validation_failure(
    raw_proposal: object,
    reason: str,
    *,
    original_text: str,
) -> dict:
    source_excerpt = ""
    if isinstance(raw_proposal, dict) and isinstance(
        raw_proposal.get("source_excerpt"), str
    ):
        source_excerpt = raw_proposal["source_excerpt"].strip()
    start = original_text.find(source_excerpt) if source_excerpt else -1
    reason_text = {
        "invalid_shape": "Annotation has an invalid structured shape",
        "workflow_noise": "Annotation contains workflow noise",
        "target_unavailable": "Annotation target is unavailable on this Purchase Line",
        "source_excerpt_not_found": "Annotation excerpt was not found in preserved source text",
        "outside_candidate_spans": "Annotation excerpt is outside the candidate evidence spans",
    }[reason]
    failure = {"source_excerpt": source_excerpt, "reason": reason_text}
    if start >= 0:
        failure["source_locator"] = {
            "kind": "text_span",
            "start": start,
            "end": start + len(source_excerpt),
        }
    return failure


def ground_free_form_candidate(payload: dict, *, original_text: str) -> dict:
    """Derive review-visible shape and exact text ranges for the GPT-5.5 contract."""
    linked_concepts = payload.get("linked_concepts")
    if not isinstance(linked_concepts, list) or not linked_concepts:
        return payload

    primary_excerpt = payload.get("primary_evidence_excerpt")
    if not isinstance(primary_excerpt, str) or not primary_excerpt:
        # Legacy linked-concept payloads continue to use whole-entry evidence.
        return {
            **payload,
            "line_type": (
                linked_concepts[0]["concept_type"]
                if len(linked_concepts) == 1
                else "bundled"
            ),
        }

    primary_span = _ground_exact_excerpt(original_text, primary_excerpt)
    supporting_spans = [
        _ground_exact_excerpt(original_text, excerpt)
        for excerpt in payload.get("supporting_evidence_excerpts", [])
    ]
    candidate_spans = [primary_span, *supporting_spans]

    for concept in linked_concepts:
        observed_text = concept.get("observed_name_text")
        if not isinstance(observed_text, str) or not _is_grounded_in_spans(
            observed_text, candidate_spans
        ):
            raise ValueError("Linked concept Observed Name Text is not candidate-grounded")

    provider_state = payload.get("provider_state")
    observed_provider_text = payload.get("observed_provider_text")
    if provider_state in {"external", "internal"}:
        if not isinstance(observed_provider_text, str) or not _is_grounded_in_spans(
            observed_provider_text, candidate_spans
        ):
            raise ValueError("Observed Provider Text is not candidate-grounded")
    elif observed_provider_text is not None:
        raise ValueError("Unknown Provider State cannot include Observed Provider Text")

    grounded_relationships = []
    for relationship in payload.get("installation_relationships", []):
        source_excerpt = relationship["source_excerpt"]
        if not _is_grounded_in_spans(source_excerpt, candidate_spans):
            raise ValueError("Installation Relationship is not candidate-grounded")
        relationship_span = _ground_exact_excerpt(original_text, source_excerpt)
        grounded_relationships.append(
            {
                **relationship,
                "source_locator": {
                    "kind": "text_span",
                    "start": relationship_span["start"],
                    "end": relationship_span["end"],
                },
            }
        )

    return {
        **payload,
        "line_type": linked_concepts[0]["concept_type"]
        if len(linked_concepts) == 1
        else "bundled",
        "primary_evidence_span": primary_span,
        "supporting_evidence_spans": supporting_spans,
        "installation_relationships": grounded_relationships,
    }


def apply_free_form_commercial_rules(payload: dict) -> dict:
    linked_concepts = payload.get("linked_concepts")
    if not isinstance(linked_concepts, list) or not linked_concepts:
        return payload

    result = dict(payload)
    source_total = _parse_money(
        payload.get("source_stated_line_total"), payload.get("currency")
    )
    if source_total is not None:
        result["price"] = _decimal_text(source_total)
        result["price_state"] = "source_stated"

    if len(linked_concepts) != 1:
        return result
    concept = linked_concepts[0]
    quantity = _parse_decimal(concept.get("quantity"))
    unit_price = _parse_money(
        concept.get("component_unit_price"), payload.get("currency")
    )
    unit = concept.get("unit")
    if quantity is None or unit_price is None or not isinstance(unit, str):
        return result

    calculated_total = quantity * unit_price
    calculation = {
        "formula": "quantity × unit price",
        "quantity": _decimal_text(quantity),
        "unit": unit,
        "unit_price": _decimal_text(unit_price),
        "result": _decimal_text(calculated_total),
    }
    result["calculation"] = calculation
    if source_total is None:
        result["price"] = calculation["result"]
        result["price_state"] = "calculated"
    elif source_total != calculated_total:
        result["variance_warning"] = {
            "calculated_total": calculation["result"],
            "source_stated_total": _decimal_text(source_total),
            "variance": _decimal_text(source_total - calculated_total),
        }
    return result


def _parse_decimal(value: object) -> Decimal | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace(",", "").strip()
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _parse_money(value: object, currency: object) -> Decimal | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace(",", "").strip()
    expected_currency = (
        currency.strip().upper()
        if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency.strip())
        else None
    )
    parts = normalized.split(maxsplit=1)
    if len(parts) == 2 and len(parts[0]) == 3 and parts[0].isalpha():
        if expected_currency is None or parts[0].upper() != expected_currency:
            return None
        normalized = parts[1]
    symbols = {"₱": "PHP", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
    if normalized and normalized[0] in symbols:
        if expected_currency != symbols[normalized[0]]:
            return None
        normalized = normalized[1:].strip()
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _ground_exact_excerpt(original_text: str, excerpt: str) -> dict:
    start = original_text.find(excerpt)
    if start < 0:
        raise ValueError("Candidate evidence excerpt was not found in preserved source text")
    return {"excerpt": excerpt, "start": start, "end": start + len(excerpt)}


def _is_grounded_in_spans(excerpt: str, spans: list[dict]) -> bool:
    return any(excerpt in span["excerpt"] for span in spans)


def _annotation_target_available(
    payload: dict, target: str, target_concept_id: str | None = None
) -> bool:
    if target == "purchase_line":
        return target_concept_id is None
    if target == "provider":
        return (
            target_concept_id is None
            and payload.get("provider_state") == "external"
            and bool(payload.get("provider_name"))
        )
    linked_concepts = payload.get("linked_concepts")
    if isinstance(linked_concepts, list) and linked_concepts:
        matching = [
            isinstance(concept, dict) and concept.get("concept_type") == target
            for concept in linked_concepts
        ]
        matching_concepts = [
            concept
            for concept, matches in zip(linked_concepts, matching, strict=True)
            if matches
        ]
        if target_concept_id is not None:
            return any(
                concept.get("concept_id") == target_concept_id
                for concept in matching_concepts
            )
        return len(matching_concepts) == 1
    return target_concept_id is None and payload.get("line_type") == target


def _count_reason(reasons: dict[str, int], reason: str) -> None:
    reasons[reason] = reasons.get(reason, 0) + 1


def apply_contractor_assigned_provider_default(
    payload: dict,
    *,
    contractor_assigned: str,
) -> dict:
    provider_name = payload.get("provider_name")
    if payload.get("provider_state") == "internal":
        return {
            **payload,
            "observed_provider_text": payload.get("observed_provider_text") or provider_name,
            "provider_name": None,
            "provider_memory_record_id": None,
            "provider_category_suggestion": None,
        }
    normalized_contractor = _normalize(contractor_assigned)
    if (
        normalized_contractor != "internal"
        and isinstance(provider_name, str)
        and _normalize(provider_name) == normalized_contractor
    ):
        return {
            **payload,
            "provider_state": "internal",
            "observed_provider_text": payload.get("observed_provider_text") or provider_name,
            "provider_name": None,
            "provider_memory_record_id": None,
            "provider_category_suggestion": None,
        }
    return payload


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
