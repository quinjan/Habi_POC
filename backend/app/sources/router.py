from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.processing.models import ProcessingJob
from backend.app.projects.models import ProjectWorkspace
from backend.app.review.schemas import ManualSourceEntryQueuedSubmission, SourceFileQueuedSubmission
from backend.app.sources.models import ManualSourceEntry, SourceSubmission
from backend.app.sources.schemas import ManualSourceEntryCreate
from backend.app.xlsx.config import XlsxProcessingConfig
from backend.app.xlsx.upload import XlsxUploadTooLarge, preserve_xlsx_upload


router = APIRouter(tags=["manual-source-entries"])


@router.post(
    "/{project_workspace_id}/source-files",
    response_model=SourceFileQueuedSubmission,
    status_code=status.HTTP_201_CREATED,
)
def create_source_file(
    project_workspace_id: int,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
) -> SourceFileQueuedSubmission:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")
    if len(files) != 1:
        raise HTTPException(status_code=422, detail="Upload exactly one .xlsx file")
    if not (files[0].filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Only .xlsx source files are supported")
    try:
        source_submission, source_file, processing_job = preserve_xlsx_upload(
            session=session,
            project_workspace_id=project_workspace.id,
            upload=files[0],
            config=XlsxProcessingConfig.from_env(),
        )
    except XlsxUploadTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    return SourceFileQueuedSubmission(
        source_submission=source_submission,
        source_file=source_file,
        processing_job=processing_job,
    )


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
