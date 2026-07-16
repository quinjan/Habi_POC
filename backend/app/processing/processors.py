import inspect
import json
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.processing.ai_extraction import (
    AiExtractionProvider,
    apply_free_form_commercial_rules,
    apply_contractor_assigned_provider_default,
    ground_free_form_candidate,
    ground_free_form_annotation_proposals,
    validate_ai_candidates,
    validate_project_memory_matches,
)
from backend.app.processing.models import ProcessingJob
from backend.app.processing.memory_context import build_project_memory_context
from backend.app.review.models import ExtractedCandidate, ReviewBatch
from backend.app.sources.models import ManualSourceEntry
from backend.app.sources.schemas import StructuredManualSourcePayload


def process_structured_manual_row(
    session: Session,
    job: ProcessingJob,
) -> tuple[ReviewBatch, list[ExtractedCandidate], dict]:
    manual_entry = session.scalar(
        select(ManualSourceEntry).where(
            ManualSourceEntry.source_submission_id == job.source_submission_id,
            ManualSourceEntry.project_workspace_id == job.project_workspace_id,
        )
    )
    if manual_entry is None or manual_entry.structured_payload is None:
        raise ValueError("Structured manual row job requires a structured Manual Source Entry")

    payload = StructuredManualSourcePayload.model_validate(
        manual_entry.structured_payload
    ).model_dump(mode="json")
    submitted_annotations = payload.pop("annotations")
    payload["annotation_proposals"] = [
        {
            "proposal_id": f"structured:annotations:{index}",
            "text": annotation["text"],
            "annotation_type": annotation["annotation_type"],
            "target": annotation["target"],
            "source_excerpt": annotation["text"],
            "source_locator": {
                "kind": "structured_field",
                "field_path": f"structured_payload.annotations[{index}].text",
            },
            "provenance": "source_field",
        }
        for index, annotation in enumerate(submitted_annotations)
    ]
    legacy_remarks = payload.get("remarks_or_terms")
    if isinstance(legacy_remarks, str) and legacy_remarks.strip() != "":
        payload["annotation_proposals"].append(
            {
                "proposal_id": "structured:remarks_or_terms",
                "text": legacy_remarks,
                "annotation_type": "general_qualifier",
                "target": "purchase_line",
                "source_excerpt": legacy_remarks,
                "source_locator": {
                    "kind": "structured_field",
                    "field_path": "structured_payload.remarks_or_terms",
                },
                "provenance": "legacy_default",
            }
        )
    review_batch = ReviewBatch(
        project_workspace_id=job.project_workspace_id,
        source_submission_id=job.source_submission_id,
        status="review_pending",
    )
    session.add(review_batch)
    session.flush()

    candidate = ExtractedCandidate(
        project_workspace_id=job.project_workspace_id,
        review_batch_id=review_batch.id,
        source_submission_id=job.source_submission_id,
        status="pending_review",
        proposed_payload=payload,
    )
    session.add(candidate)
    session.flush()

    return review_batch, [candidate], {"processor": "structured_manual_row_v1"}


def process_ai_manual_free_form(
    session: Session,
    job: ProcessingJob,
    ai_provider: AiExtractionProvider,
) -> tuple[ReviewBatch | None, list[ExtractedCandidate], dict, str, str | None]:
    provider_name = getattr(ai_provider, "provider_name", "fake")
    provider_model = getattr(
        ai_provider,
        "free_form_model",
        getattr(ai_provider, "model", "fake-ai-provider"),
    )
    manual_entry = session.scalar(
        select(ManualSourceEntry).where(
            ManualSourceEntry.source_submission_id == job.source_submission_id,
            ManualSourceEntry.project_workspace_id == job.project_workspace_id,
        )
    )
    if manual_entry is None or manual_entry.original_text is None:
        return (
            None,
            [],
            {
                "processor": "ai_manual_free_form_v1",
                "provider": provider_name,
                "model": provider_model,
                "failure_summary": "Free-form AI job requires preserved original text",
            },
            "failed",
            "Free-form AI job requires preserved original text",
        )

    memory_context, omitted_counts = build_project_memory_context(
        session=session,
        project_workspace_id=job.project_workspace_id,
        source_text=manual_entry.original_text,
        complete=True,
        include_record_ids=True,
    )
    estimated_input_chars = len(manual_entry.original_text) + len(
        json.dumps(memory_context, ensure_ascii=False, sort_keys=True)
    )
    max_input_chars = int(os.getenv("OPENAI_FREE_FORM_MAX_INPUT_CHARS", "800000"))
    if estimated_input_chars > max_input_chars:
        failure_summary = (
            "Complete selected-project memory exceeds the safe free-form model request "
            "budget, so no candidates were saved. Archive unused memory or increase the "
            "configured safe budget before trying again."
        )
        return (
            None,
            [],
            {
                "processor": "ai_manual_free_form_v1",
                "provider": provider_name,
                "model": provider_model,
                "failure": "complete_memory_context_exceeds_budget",
                "failure_summary": failure_summary,
                "estimated_input_chars": estimated_input_chars,
                "max_input_chars": max_input_chars,
                "memory_context_record_counts": {
                    "materials": len(memory_context["materials"]),
                    "services": len(memory_context["services"]),
                    "providers": len(memory_context["providers"]),
                },
            },
            "failed",
            failure_summary,
        )
    retries_enabled = _env_bool("OPENAI_FREE_FORM_RETRIES_ENABLED", default=True)
    initial_reasoning_effort = os.getenv(
        "OPENAI_FREE_FORM_REASONING_EFFORT", "high"
    ).strip()
    retry_reasoning_effort = os.getenv(
        "OPENAI_FREE_FORM_RETRY_REASONING_EFFORT", "xhigh"
    ).strip()
    max_attempts = 2 if retries_enabled else 1
    raw_candidates: list[dict] = []
    valid_payloads: list[dict] = []
    dropped_count = 0
    dropped_annotation_count = 0
    dropped_annotation_reasons: dict[str, int] = {}
    invalid_candidate_count = 0
    validation_failures: list[dict] = []
    malformed_failure: str | None = None
    attempt_count = 0
    repair_context: dict | None = None
    retry_kind: str | None = None

    for attempt_index in range(max_attempts):
        attempt_count = attempt_index + 1
        reasoning_effort = (
            initial_reasoning_effort if attempt_index == 0 else retry_reasoning_effort
        )
        try:
            raw_result = _extract_free_form_result(
                ai_provider,
                original_text=manual_entry.original_text,
                source_submission_id=job.source_submission_id,
                memory_context=memory_context,
                reasoning_effort=reasoning_effort,
                repair_context=repair_context,
            )
        except Exception as error:
            return (
                None,
                [],
                {
                    "processor": "ai_manual_free_form_v1",
                    "provider": provider_name,
                    "model": provider_model,
                    "failure": "provider_runtime_error",
                    "failure_summary": str(error),
                    "attempt_count": attempt_count,
                },
                "failed",
                str(error),
            )

        if not isinstance(raw_result, dict):
            malformed_failure = "AI provider returned malformed result"
            if attempt_index + 1 < max_attempts:
                repair_context = {
                    "kind": "whole_result_repair",
                    "message": "Return the complete batch in the required structured shape.",
                }
                retry_kind = repair_context["kind"]
                continue
            break
        raw_candidates_value = raw_result.get("candidates", [])
        if not isinstance(raw_candidates_value, list):
            malformed_failure = "AI provider returned malformed candidates"
            if attempt_index + 1 < max_attempts:
                repair_context = {
                    "kind": "whole_result_repair",
                    "message": "Return the complete candidates array in the required structured shape.",
                }
                retry_kind = repair_context["kind"]
                continue
            break
        malformed_failure = None
        raw_candidates = raw_candidates_value
        if not raw_candidates:
            if attempt_index + 1 < max_attempts:
                repair_context = {
                    "kind": "zero_confirmation",
                    "message": "Confirm that the source has no eligible candidates.",
                }
                retry_kind = repair_context["kind"]
                continue
            invalid_candidate_count = 0
            break

        candidate_payloads, dropped_count = validate_ai_candidates(
            source_submission_id=job.source_submission_id,
            raw_candidates=raw_candidates,
        )
        invalid_candidate_count = dropped_count
        grounded_payloads: list[dict] = []
        validation_failures = []
        dropped_annotation_count = 0
        dropped_annotation_reasons = {}
        for candidate_index, payload in enumerate(candidate_payloads):
            match_failures = validate_project_memory_matches(
                payload, memory_context=memory_context
            )
            if match_failures:
                invalid_candidate_count += 1
                validation_failures.extend(
                    {"candidate_index": candidate_index, **failure}
                    for failure in match_failures
                )
                continue
            try:
                grounded_candidate = ground_free_form_candidate(
                    payload,
                    original_text=manual_entry.original_text,
                )
            except ValueError as error:
                invalid_candidate_count += 1
                validation_failures.append(
                    {
                        "candidate_index": candidate_index,
                        "reason": str(error),
                        "source_excerpt": payload.get("primary_evidence_excerpt"),
                    }
                )
                continue
            grounded_candidate = apply_free_form_commercial_rules(grounded_candidate)
            grounded_payload, annotation_dropped, annotation_reasons = (
                ground_free_form_annotation_proposals(
                    grounded_candidate,
                    original_text=manual_entry.original_text,
                )
            )
            invalid_annotation_reasons = {
                reason: count
                for reason, count in annotation_reasons.items()
                if reason != "exact_duplicate"
            }
            if invalid_annotation_reasons:
                invalid_candidate_count += 1
                validation_failures.extend(
                    {
                        "candidate_index": candidate_index,
                        **failure,
                    }
                    for failure in grounded_payload.get(
                        "annotation_validation_failures", []
                    )
                )
            else:
                grounded_payloads.append(grounded_payload)
            dropped_annotation_count += annotation_dropped
            for reason, count in annotation_reasons.items():
                dropped_annotation_reasons[reason] = (
                    dropped_annotation_reasons.get(reason, 0) + count
                )

        if invalid_candidate_count:
            if attempt_index + 1 < max_attempts:
                repair_context = {
                    "kind": (
                        "candidate_local_repair"
                        if grounded_payloads and invalid_candidate_count < len(raw_candidates)
                        else "whole_result_repair"
                    ),
                    "message": (
                        "Repair the invalid candidates, then return the complete source-ordered batch."
                    ),
                    "invalid_candidate_count": invalid_candidate_count,
                    "validation_failures": validation_failures,
                }
                retry_kind = repair_context["kind"]
                continue
            break

        valid_payloads = [
            apply_contractor_assigned_provider_default(
                payload,
                contractor_assigned=memory_context["contractor_assigned"],
            )
            for payload in grounded_payloads
        ]
        break
    diagnostics = {
        "processor": "ai_manual_free_form_v1",
        "provider": provider_name,
        "model": provider_model,
        "raw_candidate_count": len(raw_candidates),
        "valid_candidate_count": len(valid_payloads),
        "dropped_candidate_count": dropped_count,
        "memory_context_record_counts": {
            "materials": len(memory_context["materials"]),
            "services": len(memory_context["services"]),
            "providers": len(memory_context["providers"]),
        },
        "estimated_input_chars": estimated_input_chars,
    }
    if attempt_count > 1:
        diagnostics["attempt_count"] = attempt_count
        diagnostics["retry_kind"] = retry_kind
    if dropped_annotation_count:
        diagnostics["dropped_annotation_count"] = dropped_annotation_count
        diagnostics["dropped_annotation_reasons"] = dropped_annotation_reasons
    if validation_failures:
        diagnostics["validation_failures"] = validation_failures
    if any(omitted_counts.values()):
        diagnostics["memory_context_omitted_counts"] = omitted_counts

    if malformed_failure is not None:
        diagnostics["failure_summary"] = malformed_failure
        return None, [], diagnostics, "failed", malformed_failure
    if not raw_candidates:
        return None, [], diagnostics, "no_candidates_found", None
    if invalid_candidate_count or not valid_payloads:
        detected_count = len(raw_candidates)
        invalid_count = invalid_candidate_count or detected_count
        failure_summary = (
            "Free-form extraction could not produce a complete grounded Review Batch. "
            f"{invalid_count} of {detected_count} detected Purchase Lines remained invalid "
            f"after {'retry' if attempt_count > 1 else 'validation'}, so no candidates were "
            "saved. Review the affected source text and try again."
        )
        diagnostics["failure_summary"] = failure_summary
        diagnostics["invalid_candidate_count"] = invalid_count
        return (
            None,
            [],
            diagnostics,
            "failed",
            failure_summary,
        )

    review_batch = ReviewBatch(
        project_workspace_id=job.project_workspace_id,
        source_submission_id=job.source_submission_id,
        status="review_pending",
    )
    session.add(review_batch)
    session.flush()

    candidates: list[ExtractedCandidate] = []
    for payload in valid_payloads:
        candidate = ExtractedCandidate(
            project_workspace_id=job.project_workspace_id,
            review_batch_id=review_batch.id,
            source_submission_id=job.source_submission_id,
            status="pending_review",
            proposed_payload=payload,
        )
        session.add(candidate)
        candidates.append(candidate)
    session.flush()

    return review_batch, candidates, diagnostics, "review_ready", None


def _extract_free_form_result(
    ai_provider: AiExtractionProvider,
    *,
    original_text: str,
    source_submission_id: int,
    memory_context: dict,
    reasoning_effort: str,
    repair_context: dict | None,
) -> object:
    extract = ai_provider.extract_purchase_lines
    parameters = inspect.signature(extract).parameters
    kwargs: dict = {
        "original_text": original_text,
        "source_submission_id": source_submission_id,
    }
    if "memory_context" in parameters:
        kwargs["memory_context"] = memory_context
    if "reasoning_effort" in parameters:
        kwargs["reasoning_effort"] = reasoning_effort
    if "repair_context" in parameters:
        kwargs["repair_context"] = repair_context
    return extract(**kwargs)


def _env_bool(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}
