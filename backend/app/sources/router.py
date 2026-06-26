from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.processing.manual import parse_free_form_manual_entry
from backend.app.processing.models import ProcessingJob
from backend.app.projects.models import ProjectWorkspace
from backend.app.review.models import ExtractedCandidate, ReviewBatch
from backend.app.review.schemas import ManualSourceEntrySubmission
from backend.app.sources.models import ManualSourceEntry, SourceSubmission, utc_now
from backend.app.sources.schemas import ManualSourceEntryCreate


router = APIRouter(tags=["manual-source-entries"])


@router.post(
    "/{project_workspace_id}/manual-source-entries",
    response_model=ManualSourceEntrySubmission,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_source_entry(
    project_workspace_id: int,
    payload: ManualSourceEntryCreate,
    session: Session = Depends(get_session),
) -> ManualSourceEntrySubmission:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")

    if payload.entry_type == "structured_row" and payload.structured_payload is None:
        raise HTTPException(
            status_code=422,
            detail="Structured manual source entries require structured_payload",
        )
    if payload.entry_type == "free_form_text" and payload.original_text is None:
        raise HTTPException(
            status_code=422,
            detail="Free-form manual source entries require original_text",
        )

    source_submission = SourceSubmission(
        project_workspace_id=project_workspace.id,
        submission_type="manual_source_entry",
        entered_by=None,
    )
    session.add(source_submission)
    session.flush()

    manual_source_entry = ManualSourceEntry(
        project_workspace_id=project_workspace.id,
        source_submission_id=source_submission.id,
        entry_type=payload.entry_type,
        structured_payload=payload.structured_payload.model_dump(mode="json")
        if payload.structured_payload
        else None,
        original_text=payload.original_text if payload.entry_type == "free_form_text" else None,
    )
    session.add(manual_source_entry)
    session.flush()

    proposed_payload = _proposed_payload_for_manual_entry(
        payload=payload,
        source_submission_id=source_submission.id,
    )
    review_batch = None
    candidate = None
    if proposed_payload is not None:
        review_batch = ReviewBatch(
            project_workspace_id=project_workspace.id,
            source_submission_id=source_submission.id,
            status="review_pending",
        )
        session.add(review_batch)
        session.flush()

        candidate = ExtractedCandidate(
            project_workspace_id=project_workspace.id,
            review_batch_id=review_batch.id,
            source_submission_id=source_submission.id,
            status="pending_review",
            proposed_payload=proposed_payload,
        )
        session.add(candidate)
        session.flush()

    finished_at = utc_now()
    processing_job = ProcessingJob(
        project_workspace_id=project_workspace.id,
        source_submission_id=source_submission.id,
        status="review_ready" if candidate is not None else "no_candidates_found",
        source_type="manual_source_entry",
        processor_name=_processor_name(payload.entry_type),
        started_at=finished_at,
        finished_at=finished_at,
        candidate_count=1 if candidate is not None else 0,
        review_batch_id=review_batch.id if review_batch is not None else None,
    )
    session.add(processing_job)
    session.commit()

    session.refresh(source_submission)
    session.refresh(manual_source_entry)
    session.refresh(processing_job)
    if review_batch is not None:
        session.refresh(review_batch)
    if candidate is not None:
        session.refresh(candidate)
    return ManualSourceEntrySubmission(
        source_submission=source_submission,
        manual_source_entry=manual_source_entry,
        processing_job=processing_job,
        review_batch=review_batch,
        candidates=[candidate] if candidate is not None else [],
    )


def _proposed_payload_for_manual_entry(
    *,
    payload: ManualSourceEntryCreate,
    source_submission_id: int,
) -> dict | None:
    if payload.entry_type == "structured_row":
        return payload.structured_payload.model_dump(mode="json") if payload.structured_payload else None
    if payload.original_text is None:
        return None
    return parse_free_form_manual_entry(
        original_text=payload.original_text,
        source_submission_id=source_submission_id,
    )


def _processor_name(entry_type: str) -> str:
    if entry_type == "structured_row":
        return "structured_manual_row_v1"
    return "manual_free_form_stub_v1"
