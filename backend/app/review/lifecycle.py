from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.review.models import (
    DuplicateCandidateGroup,
    DuplicateCandidateGroupMember,
    ExtractedCandidate,
    ReviewBatch,
)
from backend.app.review.schemas import ReviewedPurchaseLinePayload
from backend.app.sources.models import ManualSourceEntry


TERMINAL_REVIEW_BATCH_STATUSES = {"imported", "review_closed_no_import"}


class TerminalReviewBatchError(ValueError):
    pass


def apply_candidate_decision(
    *,
    session: Session,
    review_batch: ReviewBatch,
    candidate: ExtractedCandidate,
    decision: str | None,
    reviewed_payload: dict | None,
    merged_into_candidate_id: int | None = None,
) -> None:
    ensure_review_batch_editable(review_batch)
    if decision == "merged":
        _validate_merge_target(
            session=session,
            review_batch=review_batch,
            candidate=candidate,
            merged_into_candidate_id=merged_into_candidate_id,
        )

    candidate.decision = decision
    candidate.status = "pending_review" if decision is None else f"{decision}_for_import"
    candidate.reviewed_payload = reviewed_payload if decision == "approved" else None
    candidate.merged_into_candidate_id = merged_into_candidate_id if decision == "merged" else None
    recalculate_review_batch_status(session=session, review_batch=review_batch)


def recalculate_review_batch_status(*, session: Session, review_batch: ReviewBatch) -> None:
    if review_batch.status in TERMINAL_REVIEW_BATCH_STATUSES:
        return

    candidates = _get_batch_candidates(session, review_batch.id)
    decided_candidates = [candidate for candidate in candidates if candidate.decision is not None]

    if not decided_candidates:
        review_batch.status = "review_pending"
        return

    if len(decided_candidates) != len(candidates):
        review_batch.status = "review_in_progress"
        return

    if detect_duplicate_conflicts(session=session, review_batch=review_batch):
        review_batch.status = "review_in_progress"
        return

    if any(_approved_candidate_satisfies_import_gates(session, candidate) for candidate in candidates):
        review_batch.status = "ready_to_import"
        return

    review_batch.status = "review_in_progress"


def close_review_batch_with_no_import(*, session: Session, review_batch: ReviewBatch) -> None:
    ensure_review_batch_editable(review_batch)
    candidates = _get_batch_candidates(session, review_batch.id)
    if not candidates or any(candidate.decision != "rejected" for candidate in candidates):
        raise ValueError("Only fully excluded batches can be closed with no import")

    review_batch.status = "review_closed_no_import"


def ensure_review_batch_editable(review_batch: ReviewBatch) -> None:
    if review_batch.status in TERMINAL_REVIEW_BATCH_STATUSES:
        raise TerminalReviewBatchError("Terminal review batches cannot be changed")


def detect_duplicate_conflicts(*, session: Session, review_batch: ReviewBatch) -> list[str]:
    conflicts: list[str] = []
    candidates = {
        candidate.id: candidate for candidate in _get_batch_candidates(session, review_batch.id)
    }

    for duplicate_group in session.scalars(
        select(DuplicateCandidateGroup).where(
            DuplicateCandidateGroup.review_batch_id == review_batch.id
        )
    ):
        member_ids = _get_duplicate_group_member_ids(session, duplicate_group.id)
        approved_survivor_count = sum(
            1
            for member_id in member_ids
            if candidates[member_id].decision == "approved"
        )
        if approved_survivor_count > 1:
            conflicts.append("multiple_approved_survivors")

    for candidate in candidates.values():
        if candidate.decision == "merged":
            conflicts.extend(_merge_conflicts(session=session, candidate=candidate))
        elif candidate.merged_into_candidate_id is not None:
            conflicts.append("merge_target_on_non_merged_candidate")

    return _dedupe_preserving_order(conflicts)


def _merge_conflicts(*, session: Session, candidate: ExtractedCandidate) -> list[str]:
    if candidate.merged_into_candidate_id is None:
        return ["missing_merge_target"]
    if candidate.merged_into_candidate_id == candidate.id:
        return ["self_merge"]

    target = session.get(ExtractedCandidate, candidate.merged_into_candidate_id)
    if (
        target is None
        or target.project_workspace_id != candidate.project_workspace_id
        or target.review_batch_id != candidate.review_batch_id
    ):
        return ["merge_target_outside_duplicate_group"]

    candidate_group_ids = _candidate_duplicate_group_ids(session, candidate.id)
    target_group_ids = _candidate_duplicate_group_ids(session, target.id)
    if candidate_group_ids.isdisjoint(target_group_ids):
        return ["merge_target_outside_duplicate_group"]

    if _merge_chain_has_loop(session=session, candidate=candidate):
        return ["merge_loop"]

    if target.decision is None:
        return ["unresolved_merge_target"]

    return []


def _get_duplicate_group_member_ids(
    session: Session,
    duplicate_group_id: int,
) -> list[int]:
    return list(
        session.scalars(
            select(DuplicateCandidateGroupMember.candidate_id).where(
                DuplicateCandidateGroupMember.duplicate_group_id == duplicate_group_id
            )
        )
    )


def _merge_chain_has_loop(*, session: Session, candidate: ExtractedCandidate) -> bool:
    seen_candidate_ids = {candidate.id}
    next_candidate_id = candidate.merged_into_candidate_id
    while next_candidate_id is not None:
        if next_candidate_id in seen_candidate_ids:
            return True
        seen_candidate_ids.add(next_candidate_id)
        next_candidate = session.get(ExtractedCandidate, next_candidate_id)
        if next_candidate is None or next_candidate.decision != "merged":
            return False
        next_candidate_id = next_candidate.merged_into_candidate_id
    return False


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _validate_merge_target(
    *,
    session: Session,
    review_batch: ReviewBatch,
    candidate: ExtractedCandidate,
    merged_into_candidate_id: int | None,
) -> None:
    if merged_into_candidate_id is None:
        raise ValueError("Merged candidates require a merge target")

    target = session.get(ExtractedCandidate, merged_into_candidate_id)
    if (
        target is None
        or target.project_workspace_id != candidate.project_workspace_id
        or target.review_batch_id != review_batch.id
    ):
        raise ValueError("Merged candidates must target a candidate in the same duplicate group")

    candidate_group_ids = _candidate_duplicate_group_ids(session, candidate.id)
    target_group_ids = _candidate_duplicate_group_ids(session, target.id)
    if candidate_group_ids.isdisjoint(target_group_ids):
        raise ValueError("Merged candidates must target a candidate in the same duplicate group")


def _candidate_duplicate_group_ids(session: Session, candidate_id: int) -> set[int]:
    return set(
        session.scalars(
            select(DuplicateCandidateGroupMember.duplicate_group_id).where(
                DuplicateCandidateGroupMember.candidate_id == candidate_id
            )
        )
    )


def _get_batch_candidates(session: Session, review_batch_id: int) -> list[ExtractedCandidate]:
    return list(
        session.scalars(
            select(ExtractedCandidate)
            .where(ExtractedCandidate.review_batch_id == review_batch_id)
            .order_by(ExtractedCandidate.id)
        )
    )


def _approved_candidate_satisfies_import_gates(
    session: Session,
    candidate: ExtractedCandidate,
) -> bool:
    if candidate.decision != "approved" or candidate.reviewed_payload is None:
        return False

    manual_source_entry = _manual_entry_for_source_submission(
        session=session,
        source_submission_id=candidate.source_submission_id,
    )
    if (
        manual_source_entry is None
        or manual_source_entry.project_workspace_id != candidate.project_workspace_id
    ):
        return False

    payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
    return (
        payload.line_type in {"material", "service"}
        and _present(payload.name)
        and _present(payload.top_level_category)
        and _present(payload.subcategory)
    )


def _present(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _manual_entry_for_source_submission(
    *,
    session: Session,
    source_submission_id: int,
) -> ManualSourceEntry | None:
    return session.scalar(
        select(ManualSourceEntry).where(
            ManualSourceEntry.source_submission_id == source_submission_id
        )
    )
