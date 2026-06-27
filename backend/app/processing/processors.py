from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.processing.ai_extraction import (
    AiExtractionProvider,
    validate_ai_candidates,
)
from backend.app.processing.models import ProcessingJob
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

    try:
        raw_result = ai_provider.extract_purchase_lines(
            original_text=manual_entry.original_text,
            source_submission_id=job.source_submission_id,
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
    diagnostics = {
        "processor": "ai_manual_free_form_v1",
        "provider": provider_name,
        "model": provider_model,
        "raw_candidate_count": len(raw_candidates),
        "valid_candidate_count": len(valid_payloads),
        "dropped_candidate_count": dropped_count,
    }

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
