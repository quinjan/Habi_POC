from fastapi.testclient import TestClient


def create_review_ready_manual_submission(
    client: TestClient,
    *,
    project_workspace_id: int,
    structured_payload: dict,
) -> dict:
    from backend.app.processing.models import ProcessingJob
    from backend.app.review.models import ExtractedCandidate, ReviewBatch
    from backend.app.sources.models import ManualSourceEntry, SourceSubmission

    with client.app.state.session_factory() as session:
        source_submission = SourceSubmission(
            project_workspace_id=project_workspace_id,
            submission_type="manual_source_entry",
            entered_by=None,
        )
        session.add(source_submission)
        session.flush()

        manual_source_entry = ManualSourceEntry(
            project_workspace_id=project_workspace_id,
            source_submission_id=source_submission.id,
            entry_type="structured_row",
            structured_payload=structured_payload,
            original_text=None,
        )
        session.add(manual_source_entry)

        review_batch = ReviewBatch(
            project_workspace_id=project_workspace_id,
            source_submission_id=source_submission.id,
            status="review_pending",
        )
        session.add(review_batch)
        session.flush()

        candidate = ExtractedCandidate(
            project_workspace_id=project_workspace_id,
            review_batch_id=review_batch.id,
            source_submission_id=source_submission.id,
            status="pending_review",
            proposed_payload=structured_payload,
        )
        session.add(candidate)
        session.flush()

        processing_job = ProcessingJob(
            project_workspace_id=project_workspace_id,
            source_submission_id=source_submission.id,
            status="review_ready",
            source_type="manual_source_entry",
            processor_name="structured_manual_row_v1",
            candidate_count=1,
            review_batch_id=review_batch.id,
        )
        session.add(processing_job)
        session.commit()

        return {
            "source_submission": {"id": source_submission.id},
            "manual_source_entry": {"id": manual_source_entry.id},
            "processing_job": {"id": processing_job.id},
            "review_batch": {"id": review_batch.id},
            "candidates": [{"id": candidate.id}],
        }
