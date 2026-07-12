from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.processing.models import ProcessingJob
from backend.app.processing.schemas import (
    ProcessingJobDetail,
    ProcessingJobList,
    ProcessingJobListItem,
    SourceFileSummary,
    SourceSubmissionSummary,
)
from backend.app.projects.models import ProjectWorkspace
from backend.app.sources.models import SourceFile, SourceSubmission


router = APIRouter(tags=["processing-jobs"])


@router.get(
    "/{project_workspace_id}/processing-jobs",
    response_model=ProcessingJobList,
)
def list_processing_jobs(
    project_workspace_id: int,
    session: Session = Depends(get_session),
) -> ProcessingJobList:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")

    processing_jobs = session.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.project_workspace_id == project_workspace_id)
        .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
        .limit(20)
    ).all()
    source_submissions = {
        source_submission.id: source_submission
        for source_submission in session.scalars(
            select(SourceSubmission).where(
                SourceSubmission.id.in_(
                    [processing_job.source_submission_id for processing_job in processing_jobs]
                )
            )
        )
    }
    source_files = {
        source_file.source_submission_id: source_file
        for source_file in session.scalars(
            select(SourceFile).where(
                SourceFile.source_submission_id.in_(
                    [processing_job.source_submission_id for processing_job in processing_jobs]
                )
            )
        )
    }

    return ProcessingJobList(
        items=[
            ProcessingJobListItem(
                processing_job=processing_job,
                source_submission=_source_submission_summary(
                    source_submissions[processing_job.source_submission_id]
                ),
                source_file=_source_file_summary(
                    source_files.get(processing_job.source_submission_id)
                ),
                review_batch_id=processing_job.review_batch_id,
            )
            for processing_job in processing_jobs
        ]
    )


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
        source_submission=_source_submission_summary(source_submission),
        source_file=_source_file_summary(
            session.scalar(
                select(SourceFile).where(
                    SourceFile.source_submission_id == source_submission.id
                )
            )
        ),
        review_batch_id=processing_job.review_batch_id,
    )


def _source_submission_summary(source_submission: SourceSubmission) -> SourceSubmissionSummary:
    return SourceSubmissionSummary(
        id=source_submission.id,
        submission_type=source_submission.submission_type,
        submitted_at=source_submission.submitted_at,
    )


def _source_file_summary(source_file: SourceFile | None) -> SourceFileSummary | None:
    if source_file is None:
        return None
    return SourceFileSummary(
        id=source_file.id,
        original_filename=source_file.original_filename,
        byte_size=source_file.byte_size,
        declared_mime_type=source_file.declared_mime_type,
        uploaded_at=source_file.uploaded_at,
        sha256_checksum=source_file.sha256_checksum,
    )
