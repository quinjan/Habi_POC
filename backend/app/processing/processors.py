from sqlalchemy import select
from sqlalchemy.orm import Session

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
