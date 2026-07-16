from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.evidence.sources import candidate_source_evidence
from backend.app.memory.models import MemoryRecord
from backend.app.review.models import (
    DuplicateCandidateGroup,
    DuplicateCandidateGroupMember,
    ExtractedCandidate,
    ReviewBatch,
)
from backend.app.review.schemas import ReviewedPurchaseLinePayload
from backend.app.taxonomy.models import TaxonomyDecision, TaxonomyGate, TaxonomyNode


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

    approved_candidates = [candidate for candidate in candidates if candidate.decision == "approved"]
    if approved_candidates and all(
        _approved_candidate_satisfies_import_gates(session, candidate)
        for candidate in approved_candidates
    ):
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


def validate_approved_reviewed_payload(reviewed_payload: dict | None) -> None:
    if reviewed_payload is None:
        raise ValueError("Included candidates require reviewed payloads")

    payload = ReviewedPurchaseLinePayload.model_validate(reviewed_payload)
    if not _payload_has_importable_shape(payload):
        raise ValueError(
            "Included candidates require valid linked concepts and resolved category paths"
        )


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

    if candidate_source_evidence(session=session, candidate=candidate) is None:
        return False

    payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
    return (
        _payload_has_importable_shape(payload)
        and not approved_candidate_has_unresolved_taxonomy_gate(session, candidate)
    )


def approved_candidate_has_unresolved_taxonomy_gate(
    session: Session,
    candidate: ExtractedCandidate,
) -> bool:
    if candidate.decision != "approved":
        return False

    persisted_gates = list(
        session.scalars(
            select(TaxonomyGate).where(
                TaxonomyGate.candidate_id == candidate.id,
                TaxonomyGate.active.is_(True),
            )
        )
    )
    if persisted_gates:
        return any(gate.status != "accepted" for gate in persisted_gates)

    reviewed_subjects = _reviewed_taxonomy_subjects_by_type(candidate)
    for subject_type, suggestion in _candidate_taxonomy_suggestions(candidate):
        reviewed_subject = reviewed_subjects.get(subject_type)
        if reviewed_subject is None:
            continue
        reviewed_name, reviewed_top_level, reviewed_subcategory = reviewed_subject
        if _existing_memory_record(
            session=session,
            project_workspace_id=candidate.project_workspace_id,
            record_type=subject_type,
            name=reviewed_name,
        ) is not None:
            continue

        top_level_category = suggestion.get("top_level_category")
        subcategory = suggestion.get("subcategory")
        if not isinstance(top_level_category, str) or not _present(top_level_category):
            continue
        suggested_path_key = normalized_taxonomy_path_key(
            top_level_category,
            subcategory if isinstance(subcategory, str) else None,
        )
        reviewed_path_key = normalized_taxonomy_path_key(
            reviewed_top_level,
            reviewed_subcategory,
        )
        if reviewed_path_key != suggested_path_key:
            continue

        decision = latest_taxonomy_decision_for_path(
            session=session,
            project_workspace_id=candidate.project_workspace_id,
            normalized_path_key=suggested_path_key,
        )
        if decision is not None and decision.decision in {"approved", "mapped"}:
            continue
        if taxonomy_leaf_node_for_path(
            session=session,
            project_workspace_id=candidate.project_workspace_id,
            top_level_category=top_level_category,
            subcategory=subcategory if isinstance(subcategory, str) else None,
        ) is None:
            return True
    return False


def latest_taxonomy_decision_for_path(
    *,
    session: Session,
    project_workspace_id: int,
    normalized_path_key: str,
) -> TaxonomyDecision | None:
    return session.scalar(
        select(TaxonomyDecision)
        .where(
            TaxonomyDecision.project_workspace_id == project_workspace_id,
            TaxonomyDecision.normalized_suggested_path_key == normalized_path_key,
            TaxonomyDecision.superseded.is_(False),
        )
        .order_by(TaxonomyDecision.id.desc())
    )


def top_level_taxonomy_node_for_name(
    *,
    session: Session,
    project_workspace_id: int,
    name: str,
) -> TaxonomyNode | None:
    normalized_name = _normalize(name)
    return next(
        (
            taxonomy_node
            for taxonomy_node in session.scalars(
                select(TaxonomyNode).where(
                    TaxonomyNode.project_workspace_id == project_workspace_id,
                    TaxonomyNode.parent_id.is_(None),
                )
            )
            if _normalize(taxonomy_node.name) == normalized_name
        ),
        None,
    )


def taxonomy_leaf_node_for_path(
    *,
    session: Session,
    project_workspace_id: int,
    top_level_category: str,
    subcategory: str | None,
) -> TaxonomyNode | None:
    if not _present(subcategory):
        return None

    top_level = top_level_taxonomy_node_for_name(
        session=session,
        project_workspace_id=project_workspace_id,
        name=top_level_category,
    )
    if top_level is None:
        return None

    normalized_subcategory = _normalize(subcategory or "")
    return next(
        (
            taxonomy_node
            for taxonomy_node in session.scalars(
                select(TaxonomyNode).where(
                    TaxonomyNode.project_workspace_id == project_workspace_id,
                    TaxonomyNode.parent_id == top_level.id,
                )
            )
            if _normalize(taxonomy_node.name) == normalized_subcategory
        ),
        None,
    )


def _present(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _candidate_taxonomy_suggestions(
    candidate: ExtractedCandidate,
) -> list[tuple[str, dict]]:
    suggestions: list[tuple[str, dict]] = []
    linked_concepts = candidate.proposed_payload.get("linked_concepts")
    if isinstance(linked_concepts, list):
        for concept in linked_concepts:
            if not isinstance(concept, dict):
                continue
            concept_type = concept.get("concept_type")
            suggestion = concept.get("category_suggestion")
            if concept_type in {"material", "service"} and isinstance(suggestion, dict):
                suggestions.append((concept_type, suggestion))
        if candidate.proposed_payload.get("provider_state") == "external":
            provider_suggestion = candidate.proposed_payload.get(
                "provider_category_suggestion"
            )
            if isinstance(provider_suggestion, dict):
                suggestions.append(("provider", provider_suggestion))
        return suggestions

    line_type = candidate.proposed_payload.get("line_type")
    suggestion = candidate.proposed_payload.get("category_suggestion")
    if line_type in {"material", "service"} and isinstance(suggestion, dict):
        suggestions.append((line_type, suggestion))
    return suggestions


def _reviewed_taxonomy_subjects_by_type(
    candidate: ExtractedCandidate,
) -> dict[str, tuple[str, str, str]]:
    if candidate.reviewed_payload is None:
        return {}
    payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
    subjects = {
        concept.concept_type: (
            concept.name or "",
            concept.top_level_category or "",
            concept.subcategory or "",
        )
        for concept in payload.concepts()
        if _present(concept.name)
        and _present(concept.top_level_category)
        and _present(concept.subcategory)
    }
    if (
        payload.provider_state == "external"
        and _present(payload.provider_name)
        and _present(payload.provider_top_level_category)
        and _present(payload.provider_subcategory)
    ):
        subjects["provider"] = (
            payload.provider_name or "",
            payload.provider_top_level_category or "",
            payload.provider_subcategory or "",
        )
    return subjects


def _existing_memory_record(
    *,
    session: Session,
    project_workspace_id: int,
    record_type: str,
    name: str,
) -> MemoryRecord | None:
    return session.scalar(
        select(MemoryRecord).where(
            MemoryRecord.project_workspace_id == project_workspace_id,
            MemoryRecord.record_type == record_type,
            MemoryRecord.normalized_name == _normalize(name),
            MemoryRecord.status == "active",
        )
    )


def _payload_has_importable_shape(payload: ReviewedPurchaseLinePayload) -> bool:
    concepts = payload.concepts()
    concept_types = {concept.concept_type for concept in concepts}
    if len(concepts) not in {1, 2} or len(concept_types) != len(concepts):
        return False
    if len(concepts) == 2 and concept_types != {"material", "service"}:
        return False
    if any(
        not _present(concept.name)
        or not _present(concept.top_level_category)
        or not _present(concept.subcategory)
        for concept in concepts
    ):
        return False
    if payload.provider_state == "external":
        return (
            _present(payload.provider_name)
            and _present(payload.provider_top_level_category)
            and _present(payload.provider_subcategory)
        )
    if payload.provider_state == "unknown":
        return not any(
            _present(value)
            for value in (
                payload.provider_name,
                payload.provider_top_level_category,
                payload.provider_subcategory,
            )
        )
    return True


def normalized_taxonomy_path_key(
    top_level_category: str,
    subcategory: str | None,
) -> str:
    segments = [_normalize(top_level_category)]
    if _present(subcategory):
        segments.append(_normalize(subcategory or ""))
    return " / ".join(segments)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
