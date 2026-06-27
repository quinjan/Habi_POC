from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.processing.models import ProcessingJob
from backend.app.projects.models import ProjectWorkspace
from backend.app.review.schemas import ManualSourceEntryQueuedSubmission
from backend.app.sources.models import ManualSourceEntry, SourceSubmission
from backend.app.sources.schemas import ManualSourceEntryCreate


router = APIRouter(tags=["manual-source-entries"])


@router.post(
    "/{project_workspace_id}/manual-source-entries",
    response_model=ManualSourceEntryQueuedSubmission,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_source_entry(
    project_workspace_id: int,
    payload: ManualSourceEntryCreate,
    session: Session = Depends(get_session),
) -> ManualSourceEntryQueuedSubmission:
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

    processing_job = ProcessingJob(
        project_workspace_id=project_workspace.id,
        source_submission_id=source_submission.id,
        status="queued",
        source_type="manual_source_entry",
        processor_name=_processor_name(payload.entry_type),
        candidate_count=0,
        review_batch_id=None,
    )
    session.add(processing_job)
    session.commit()

    session.refresh(source_submission)
    session.refresh(manual_source_entry)
    session.refresh(processing_job)
    return ManualSourceEntryQueuedSubmission(
        source_submission=source_submission,
        manual_source_entry=manual_source_entry,
        processing_job=processing_job,
    )


def _processor_name(entry_type: str) -> str:
    if entry_type == "structured_row":
        return "structured_manual_row_v1"
    return "ai_manual_free_form_v1"
