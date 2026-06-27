import time

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.processing.models import ProcessingJob
from backend.app.processing.processors import process_structured_manual_row
from backend.app.sources.models import utc_now


SUPPORTED_PROCESSOR_NAMES = ("structured_manual_row_v1",)


def run_once(session_factory: sessionmaker) -> int:
    claimed_job_id: int | None = None
    with session_factory() as session, session.begin():
        job = session.scalar(
            select(ProcessingJob)
            .where(
                ProcessingJob.status == "queued",
                ProcessingJob.processor_name.in_(SUPPORTED_PROCESSOR_NAMES),
            )
            .order_by(ProcessingJob.created_at, ProcessingJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return 0
        job.status = "processing"
        job.started_at = utc_now()
        claimed_job_id = job.id

    with session_factory() as session, session.begin():
        job = session.get(ProcessingJob, claimed_job_id)
        if job is None:
            raise ValueError("Claimed Processing Job disappeared before processing")
        review_batch, candidates, diagnostics = process_structured_manual_row(session, job)
        job.status = "review_ready"
        job.finished_at = utc_now()
        job.candidate_count = len(candidates)
        job.review_batch_id = review_batch.id
        job.diagnostics = diagnostics

    return 1


def run_loop(session_factory: sessionmaker, *, poll_interval_seconds: float = 2.0) -> None:
    while True:
        processed = run_once(session_factory)
        if processed == 0:
            time.sleep(poll_interval_seconds)
