from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.processing.models import ProcessingJob
from backend.app.processing.schemas import (
    ProcessingJobDetail,
    SourceSubmissionSummary,
)
from backend.app.projects.models import ProjectWorkspace
from backend.app.sources.models import SourceSubmission


router = APIRouter(tags=["processing-jobs"])


@router.get(
    "/{project_workspace_id}/processing-jobs/{processing_job_id}",
    response_model=ProcessingJobDetail,
)
def get_processing_job(
    project_workspace_id: int,
    processing_job_id: int,
    session: Session = Depends(get_session),
) -> ProcessingJobDetail:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")

    processing_job = session.scalar(
        select(ProcessingJob).where(
            ProcessingJob.id == processing_job_id,
            ProcessingJob.project_workspace_id == project_workspace_id,
        )
    )
    if processing_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing job not found")

    source_submission = session.get(SourceSubmission, processing_job.source_submission_id)
    if source_submission is None or source_submission.project_workspace_id != project_workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing job not found")

    return ProcessingJobDetail(
        processing_job=processing_job,
        source_submission=SourceSubmissionSummary(
            id=source_submission.id,
            submission_type=source_submission.submission_type,
            submitted_at=source_submission.submitted_at,
        ),
        review_batch_id=processing_job.review_batch_id,
    )
