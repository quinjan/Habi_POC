import time

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.evidence import models as evidence_models  # noqa: F401
from backend.app.memory import models as memory_models  # noqa: F401
from backend.app.processing.models import ProcessingJob
from backend.app.processing.processors import (
    process_ai_manual_free_form,
    process_structured_manual_row,
)
from backend.app.projects import models as projects_models  # noqa: F401
from backend.app.review import models as review_models  # noqa: F401
from backend.app.sources.models import utc_now
from backend.app.taxonomy import models as taxonomy_models  # noqa: F401


STRUCTURED_PROCESSOR_NAME = "structured_manual_row_v1"
AI_FREE_FORM_PROCESSOR_NAME = "ai_manual_free_form_v1"


def run_once(session_factory: sessionmaker, *, ai_provider=None, ai_provider_factory=None) -> int:
    if ai_provider is None and ai_provider_factory is not None:
        ai_provider = ai_provider_factory()

    supported_processor_names = [STRUCTURED_PROCESSOR_NAME]
    if ai_provider is not None:
        supported_processor_names.append(AI_FREE_FORM_PROCESSOR_NAME)

    claimed_job_id: int | None = None
    with session_factory() as session, session.begin():
        job = session.scalar(
            select(ProcessingJob)
            .where(
                ProcessingJob.status == "queued",
                ProcessingJob.processor_name.in_(supported_processor_names),
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
        if job.processor_name == AI_FREE_FORM_PROCESSOR_NAME:
            if ai_provider is None:
                raise ValueError("AI provider is required for free-form AI processing")
            (
                review_batch,
                candidates,
                diagnostics,
                terminal_status,
                error_message,
            ) = process_ai_manual_free_form(session, job, ai_provider)
        else:
            review_batch, candidates, diagnostics = process_structured_manual_row(session, job)
            terminal_status = "review_ready"
            error_message = None

        job.status = terminal_status
        job.finished_at = utc_now()
        job.candidate_count = len(candidates)
        job.review_batch_id = review_batch.id if review_batch is not None else None
        job.error_message = error_message
        job.diagnostics = diagnostics

    return 1


def run_loop(
    session_factory: sessionmaker,
    *,
    poll_interval_seconds: float = 2.0,
    ai_provider=None,
    ai_provider_factory=None,
) -> None:
    while True:
        processed = run_once(
            session_factory,
            ai_provider=ai_provider,
            ai_provider_factory=ai_provider_factory,
        )
        if processed == 0:
            time.sleep(poll_interval_seconds)
