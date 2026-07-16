import inspect

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.processing.ai_extraction import (
    AiExtractionProvider,
    apply_contractor_assigned_provider_default,
    ground_free_form_annotation_proposals,
    validate_ai_candidates,
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
    provider_model = getattr(ai_provider, "model", "fake-ai-provider")
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
    )
    try:
        extract = ai_provider.extract_purchase_lines
        kwargs = {
            "original_text": manual_entry.original_text,
            "source_submission_id": job.source_submission_id,
        }
        if "memory_context" in inspect.signature(extract).parameters:
            kwargs["memory_context"] = memory_context
        raw_result = extract(**kwargs)
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
            },
            "failed",
            str(error),
        )
    if not isinstance(raw_result, dict):
        return (
            None,
            [],
            {
                "processor": "ai_manual_free_form_v1",
                "provider": provider_name,
                "model": provider_model,
                "failure_summary": "AI provider returned malformed result",
            },
            "failed",
            "AI provider returned malformed result",
        )

    raw_candidates = raw_result.get("candidates", [])
    if not isinstance(raw_candidates, list):
        return (
            None,
            [],
            {
                "processor": "ai_manual_free_form_v1",
                "provider": provider_name,
                "model": provider_model,
                "failure_summary": "AI provider returned malformed candidates",
            },
            "failed",
            "AI provider returned malformed candidates",
        )

    valid_payloads, dropped_count = validate_ai_candidates(
        source_submission_id=job.source_submission_id,
        raw_candidates=raw_candidates,
    )
    grounded_payloads: list[dict] = []
    dropped_annotation_count = 0
    dropped_annotation_reasons: dict[str, int] = {}
    for payload in valid_payloads:
        grounded_payload, annotation_dropped, annotation_reasons = (
            ground_free_form_annotation_proposals(
                payload,
                original_text=manual_entry.original_text,
            )
        )
        grounded_payloads.append(grounded_payload)
        dropped_annotation_count += annotation_dropped
        for reason, count in annotation_reasons.items():
            dropped_annotation_reasons[reason] = (
                dropped_annotation_reasons.get(reason, 0) + count
            )
    valid_payloads = grounded_payloads
    valid_payloads = [
        apply_contractor_assigned_provider_default(
            payload,
            contractor_assigned=memory_context["contractor_assigned"],
        )
        for payload in valid_payloads
    ]
    diagnostics = {
        "processor": "ai_manual_free_form_v1",
        "provider": provider_name,
        "model": provider_model,
        "raw_candidate_count": len(raw_candidates),
        "valid_candidate_count": len(valid_payloads),
        "dropped_candidate_count": dropped_count,
    }
    if dropped_annotation_count:
        diagnostics["dropped_annotation_count"] = dropped_annotation_count
        diagnostics["dropped_annotation_reasons"] = dropped_annotation_reasons
    annotation_limit_omitted = dropped_annotation_reasons.get("annotation_limit", 0)
    if annotation_limit_omitted:
        annotation_detected = sum(
            len(payload.get("annotation_proposals", []))
            + int(payload.get("annotation_omitted_count", 0))
            for payload in valid_payloads
        )
        diagnostics["warning_summary"] = (
            "Annotation extraction limit reached — 20 of "
            f"{annotation_detected} source-grounded annotation proposals were retained. "
            "Review the source and add any omitted qualifiers that matter."
        )
    if any(omitted_counts.values()):
        diagnostics["memory_context_omitted_counts"] = omitted_counts

    if not raw_candidates:
        return None, [], diagnostics, "no_candidates_found", None
    if not valid_payloads:
        diagnostics["failure_summary"] = "AI extraction produced no valid candidates"
        return (
            None,
            [],
            diagnostics,
            "failed",
            "AI extraction produced no valid candidates",
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
