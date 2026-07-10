from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProcessingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    source_submission_id: int
    status: str
    source_type: str
    processor_name: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    diagnostics: dict | None
    candidate_count: int
    review_batch_id: int | None


class SourceSubmissionSummary(BaseModel):
    id: int
    submission_type: str
    submitted_at: datetime


class SourceFileSummary(BaseModel):
    id: int
    original_filename: str
    byte_size: int
    declared_mime_type: str | None
    uploaded_at: datetime
    sha256_checksum: str


class ProcessingJobDetail(BaseModel):
    processing_job: ProcessingJobRead
    source_submission: SourceSubmissionSummary
    source_file: SourceFileSummary | None = None
    review_batch_id: int | None


class ProcessingJobListItem(BaseModel):
    processing_job: ProcessingJobRead
    source_submission: SourceSubmissionSummary
    source_file: SourceFileSummary | None = None
    review_batch_id: int | None


class ProcessingJobList(BaseModel):
    items: list[ProcessingJobListItem]
