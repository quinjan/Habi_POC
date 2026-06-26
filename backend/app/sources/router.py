from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.projects.models import ProjectWorkspace
from backend.app.review.models import ExtractedCandidate, ReviewBatch
from backend.app.review.schemas import ManualSourceEntrySubmission
from backend.app.sources.models import ManualSourceEntry
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

    proposed_payload = payload.model_dump(mode="json")
    manual_source_entry = ManualSourceEntry(
        project_workspace_id=project_workspace.id,
        structured_payload=proposed_payload,
    )
    session.add(manual_source_entry)
    session.flush()

    review_batch = ReviewBatch(
        project_workspace_id=project_workspace.id,
        manual_source_entry_id=manual_source_entry.id,
        status="review_pending",
    )
    session.add(review_batch)
    session.flush()

    candidate = ExtractedCandidate(
        project_workspace_id=project_workspace.id,
        review_batch_id=review_batch.id,
        manual_source_entry_id=manual_source_entry.id,
        status="pending_review",
        proposed_payload=proposed_payload,
    )
    session.add(candidate)
    session.commit()

    session.refresh(manual_source_entry)
    session.refresh(review_batch)
    session.refresh(candidate)
    return ManualSourceEntrySubmission(
        manual_source_entry=manual_source_entry,
        review_batch=review_batch,
        candidate=candidate,
    )
