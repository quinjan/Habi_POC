from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.evidence.models import (
    EvidenceAnnotation,
    EvidenceRecord,
    MemoryRecordEvidenceLink,
)
from backend.app.evidence.sources import CandidateSourceEvidence, candidate_source_evidence
from backend.app.memory.models import (
    Material,
    MemoryRecord,
    Provider,
    PurchaseLine,
    PurchaseLineConceptLink,
    Service,
)
from backend.app.processing.models import ProcessingJob
from backend.app.processing.schemas import SourceFileSummary
from backend.app.projects.models import ProjectWorkspace
from backend.app.review.lifecycle import (
    TerminalReviewBatchError,
    apply_candidate_decision,
    approved_candidate_has_unresolved_taxonomy_gate,
    close_review_batch_with_no_import,
    detect_duplicate_conflicts,
    latest_taxonomy_decision_for_path,
    normalized_taxonomy_path_key,
    recalculate_review_batch_status,
    taxonomy_leaf_node_for_path,
    validate_annotation_source_grounding,
    validate_approved_reviewed_payload,
)
from backend.app.review.models import (
    DuplicateCandidateGroup,
    DuplicateCandidateGroupMember,
    ExtractedCandidate,
    ReviewBatch,
)
from backend.app.review.schemas import (
    CandidateDecisionRequest,
    CandidateTaxonomyGateRead,
    DuplicateCandidateGroupCreate,
    DuplicateCandidateGroupMembersRequest,
    DuplicateCandidateGroupRead,
    ExistingMemoryMatchRead,
    ExtractedCandidateRead,
    ImportedPurchaseLine,
    ImportReviewBatchResponse,
    ReviewBatchDraftSaveRequest,
    ReviewBatchDetail,
    ReviewBatchRead,
    ReviewBatchTaxonomyMappingRequest,
    ReviewedPurchaseLinePayload,
    TaxonomyDecisionCreate,
    TaxonomyDecisionRead,
    TaxonomyDefaultRead,
    TaxonomyGateRead,
    TaxonomyGateReviewerDraftSaveRequest,
    TaxonomyGateReviewerDraftSaveResponse,
    TaxonomyGateSelectionRequest,
    TaxonomyNodeListRead,
    TaxonomyNodePathRead,
    TaxonomyNodeUpdate,
)
from backend.app.sources.models import SourceFile
from backend.app.taxonomy.models import (
    TaxonomyDecision,
    TaxonomyGate,
    TaxonomyNode,
    normalize_taxonomy_name,
)


router = APIRouter(tags=["review-batches"])


@router.get(
    "/{project_workspace_id}/taxonomy-nodes",
    response_model=TaxonomyNodeListRead,
)
def list_taxonomy_nodes(
    project_workspace_id: int,
    leaf_only: bool = False,
    session: Session = Depends(get_session),
) -> TaxonomyNodeListRead:
    _ensure_project_workspace_exists(session, project_workspace_id)
    nodes = list(
        session.scalars(
            select(TaxonomyNode)
            .where(TaxonomyNode.project_workspace_id == project_workspace_id)
            .order_by(TaxonomyNode.id)
        )
    )
    node_ids_with_children = {node.parent_id for node in nodes if node.parent_id is not None}
    items: list[TaxonomyNodePathRead] = []
    for node in nodes:
        if leaf_only and (node.parent_id is None or node.id in node_ids_with_children):
            continue
        path = _taxonomy_node_path(session, node.id)
        if path is None:
            continue
        items.append(
            TaxonomyNodePathRead(
                id=node.id,
                name=node.name,
                parent_id=node.parent_id,
                path=path,
            )
        )
    return TaxonomyNodeListRead(items=items)


@router.patch(
    "/{project_workspace_id}/taxonomy-nodes/{taxonomy_node_id}",
    response_model=TaxonomyNodePathRead,
)
def update_taxonomy_node(
    project_workspace_id: int,
    taxonomy_node_id: int,
    payload: TaxonomyNodeUpdate,
    session: Session = Depends(get_session),
) -> TaxonomyNodePathRead:
    _ensure_project_workspace_exists(session, project_workspace_id)
    taxonomy_node = session.get(TaxonomyNode, taxonomy_node_id)
    if taxonomy_node is None or taxonomy_node.project_workspace_id != project_workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy node not found")

    cleaned_name = payload.name.strip()
    if not cleaned_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taxonomy node name cannot be blank",
        )
    _ensure_unique_taxonomy_sibling_name(
        session=session,
        project_workspace_id=project_workspace_id,
        parent_id=taxonomy_node.parent_id,
        normalized_name=normalize_taxonomy_name(cleaned_name),
        exclude_taxonomy_node_id=taxonomy_node.id,
    )
    taxonomy_node.name = cleaned_name
    taxonomy_node.normalized_name = normalize_taxonomy_name(cleaned_name)
    session.flush()
    session.commit()
    session.refresh(taxonomy_node)
    path = _taxonomy_node_path(session, taxonomy_node.id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy node not found")
    return TaxonomyNodePathRead(
        id=taxonomy_node.id,
        name=taxonomy_node.name,
        parent_id=taxonomy_node.parent_id,
        path=path,
    )


@router.get(
    "/{project_workspace_id}/review-batches/{review_batch_id}",
    response_model=ReviewBatchDetail,
)
def get_review_batch(
    project_workspace_id: int,
    review_batch_id: int,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    for candidate in _get_batch_candidates(session, review_batch.id):
        _ensure_candidate_taxonomy_gates(session, candidate)
    session.commit()
    return _review_batch_detail(session, review_batch)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/candidates/{candidate_id}/decision",
    response_model=ExtractedCandidateRead,
)
def decide_candidate(
    project_workspace_id: int,
    review_batch_id: int,
    candidate_id: int,
    payload: CandidateDecisionRequest,
    session: Session = Depends(get_session),
) -> ExtractedCandidateRead:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    candidate = session.scalar(
        select(ExtractedCandidate).where(
            ExtractedCandidate.id == candidate_id,
            ExtractedCandidate.review_batch_id == review_batch.id,
            ExtractedCandidate.project_workspace_id == project_workspace_id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    _ensure_candidate_taxonomy_gates(session, candidate)

    try:
        reviewed_payload = (
            payload.reviewed_payload.model_dump(mode="json")
            if payload.reviewed_payload
            else None
        )
        validate_annotation_source_grounding(
            candidate=candidate,
            reviewed_payload=reviewed_payload,
        )
        apply_candidate_decision(
            session=session,
            review_batch=review_batch,
            candidate=candidate,
            decision=payload.decision,
            reviewed_payload=reviewed_payload,
            merged_into_candidate_id=payload.merged_into_candidate_id,
        )
        _ensure_candidate_taxonomy_gates(session, candidate)
    except TerminalReviewBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    session.commit()
    session.refresh(candidate)
    return _candidate_read(session, candidate)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-gates/{taxonomy_gate_id}/accept",
    response_model=ReviewBatchDetail,
)
def accept_taxonomy_gate(
    project_workspace_id: int,
    review_batch_id: int,
    taxonomy_gate_id: int,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    taxonomy_gate = session.scalar(
        select(TaxonomyGate).where(
            TaxonomyGate.id == taxonomy_gate_id,
            TaxonomyGate.project_workspace_id == project_workspace_id,
            TaxonomyGate.review_batch_id == review_batch_id,
        )
    )
    if taxonomy_gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy gate not found")
    if not taxonomy_gate.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive taxonomy gates cannot be accepted",
        )
    if taxonomy_gate.status == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Taxonomy gate is already accepted",
        )

    if taxonomy_gate.selected_proposal == "reviewer_draft":
        top_level_category = taxonomy_gate.reviewer_draft_top_level_category
        subcategory = taxonomy_gate.reviewer_draft_subcategory
    else:
        top_level_category = taxonomy_gate.original_top_level_category
        subcategory = taxonomy_gate.original_subcategory
    if not _present(top_level_category) or not _present(subcategory):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taxonomy gate acceptance requires a selected two-level category path",
        )

    resolved_leaf = _approve_taxonomy_path(
        session=session,
        project_workspace_id=project_workspace_id,
        top_level_category=top_level_category or "",
        subcategory=subcategory or "",
    )
    decision = TaxonomyDecision(
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch_id,
        suggested_top_level_category=taxonomy_gate.original_top_level_category,
        suggested_subcategory=taxonomy_gate.original_subcategory,
        normalized_suggested_path_key=taxonomy_gate.normalized_original_path_key,
        decision=(
            "approved" if taxonomy_gate.selected_proposal == "ai_suggestion" else "mapped"
        ),
        resolved_taxonomy_node_id=resolved_leaf.id,
        taxonomy_gate_id=taxonomy_gate.id,
        candidate_id=taxonomy_gate.candidate_id,
        subject_type=taxonomy_gate.subject_type,
        subject_name=taxonomy_gate.subject_name,
        accepted_source=taxonomy_gate.selected_proposal,
    )
    session.add(decision)
    taxonomy_gate.status = "accepted"
    _apply_accepted_gate_category(
        session=session,
        taxonomy_gate=taxonomy_gate,
        top_level_category=top_level_category or "",
        subcategory=subcategory or "",
    )
    session.flush()
    recalculate_review_batch_status(session=session, review_batch=review_batch)
    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)


@router.put(
    "/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-gates/{taxonomy_gate_id}/reviewer-draft",
    response_model=TaxonomyGateReviewerDraftSaveResponse,
)
def save_taxonomy_gate_reviewer_draft(
    project_workspace_id: int,
    review_batch_id: int,
    taxonomy_gate_id: int,
    payload: TaxonomyGateReviewerDraftSaveRequest,
    session: Session = Depends(get_session),
) -> TaxonomyGateReviewerDraftSaveResponse:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    taxonomy_gate = session.scalar(
        select(TaxonomyGate).where(
            TaxonomyGate.id == taxonomy_gate_id,
            TaxonomyGate.project_workspace_id == project_workspace_id,
            TaxonomyGate.review_batch_id == review_batch_id,
        )
    )
    if taxonomy_gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy gate not found")
    if not taxonomy_gate.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive taxonomy gates cannot be changed",
        )
    if taxonomy_gate.status == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted taxonomy gates must be edited before saving a draft",
        )

    taxonomy_gate.reviewer_draft_top_level_category = payload.top_level_category.strip()
    taxonomy_gate.reviewer_draft_subcategory = payload.subcategory.strip()
    taxonomy_gate.selected_proposal = "reviewer_draft"
    taxonomy_gate.status = "needs_decision"
    affected_count = 0
    if payload.apply_to_similar:
        similar_pending_gates = list(
            session.scalars(
                select(TaxonomyGate).where(
                    TaxonomyGate.review_batch_id == review_batch_id,
                    TaxonomyGate.id != taxonomy_gate.id,
                    TaxonomyGate.subject_type == taxonomy_gate.subject_type,
                    TaxonomyGate.normalized_original_path_key
                    == taxonomy_gate.normalized_original_path_key,
                    TaxonomyGate.status == "needs_decision",
                    TaxonomyGate.active.is_(True),
                )
            )
        )
        for similar_gate in similar_pending_gates:
            similar_gate.reviewer_draft_top_level_category = payload.top_level_category.strip()
            similar_gate.reviewer_draft_subcategory = payload.subcategory.strip()
            similar_gate.selected_proposal = "reviewer_draft"
        affected_count = len(similar_pending_gates)
    recalculate_review_batch_status(session=session, review_batch=review_batch)
    session.commit()
    session.refresh(review_batch)
    return TaxonomyGateReviewerDraftSaveResponse(
        review_batch=_review_batch_detail(session, review_batch),
        affected_count=affected_count,
    )


@router.put(
    "/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-gates/{taxonomy_gate_id}/selection",
    response_model=ReviewBatchDetail,
)
def select_taxonomy_gate_proposal(
    project_workspace_id: int,
    review_batch_id: int,
    taxonomy_gate_id: int,
    payload: TaxonomyGateSelectionRequest,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    taxonomy_gate = session.scalar(
        select(TaxonomyGate).where(
            TaxonomyGate.id == taxonomy_gate_id,
            TaxonomyGate.project_workspace_id == project_workspace_id,
            TaxonomyGate.review_batch_id == review_batch_id,
        )
    )
    if taxonomy_gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy gate not found")
    if not taxonomy_gate.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive taxonomy gates cannot be changed",
        )
    if taxonomy_gate.status == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted taxonomy gates must be edited before changing selection",
        )
    if payload.selected_proposal == "reviewer_draft" and not _present(
        taxonomy_gate.reviewer_draft_top_level_category
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taxonomy gate has no reviewer draft to select",
        )

    taxonomy_gate.selected_proposal = payload.selected_proposal
    taxonomy_gate.status = "needs_decision"
    recalculate_review_batch_status(session=session, review_batch=review_batch)
    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-gates/{taxonomy_gate_id}/edit",
    response_model=ReviewBatchDetail,
)
def edit_accepted_taxonomy_gate(
    project_workspace_id: int,
    review_batch_id: int,
    taxonomy_gate_id: int,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    taxonomy_gate = session.scalar(
        select(TaxonomyGate).where(
            TaxonomyGate.id == taxonomy_gate_id,
            TaxonomyGate.project_workspace_id == project_workspace_id,
            TaxonomyGate.review_batch_id == review_batch_id,
        )
    )
    if taxonomy_gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy gate not found")
    if not taxonomy_gate.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive taxonomy gates cannot be changed",
        )
    if taxonomy_gate.status != "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only accepted taxonomy gates can be edited",
        )

    active_decisions = list(
        session.scalars(
            select(TaxonomyDecision).where(
                TaxonomyDecision.taxonomy_gate_id == taxonomy_gate.id,
                TaxonomyDecision.superseded.is_(False),
            )
        )
    )
    for decision in active_decisions:
        decision.superseded = True
        decision.superseded_at = datetime.now(timezone.utc)
    taxonomy_gate.status = "needs_decision"
    recalculate_review_batch_status(session=session, review_batch=review_batch)
    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)


@router.put(
    "/{project_workspace_id}/review-batches/{review_batch_id}/review-draft",
    response_model=ReviewBatchDetail,
)
def save_review_batch_draft(
    project_workspace_id: int,
    review_batch_id: int,
    payload: ReviewBatchDraftSaveRequest,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    candidates_by_id = {
        candidate.id: candidate
        for candidate in _get_batch_candidates(session, review_batch.id)
    }
    requested_ids = [item.candidate_id for item in payload.candidates]
    if len(set(requested_ids)) != len(requested_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review draft cannot contain duplicate candidates",
        )
    if set(requested_ids) != set(candidates_by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review draft must include every candidate in the Review Batch",
        )

    try:
        for item in payload.candidates:
            reviewed_payload = (
                item.reviewed_payload.model_dump(mode="json")
                if item.reviewed_payload is not None
                else None
            )
            if item.included:
                validate_annotation_source_grounding(
                    candidate=candidates_by_id[item.candidate_id],
                    reviewed_payload=reviewed_payload,
                )
                validate_approved_reviewed_payload(reviewed_payload)
                apply_candidate_decision(
                    session=session,
                    review_batch=review_batch,
                    candidate=candidates_by_id[item.candidate_id],
                    decision="approved",
                    reviewed_payload=reviewed_payload,
                )
            else:
                apply_candidate_decision(
                    session=session,
                    review_batch=review_batch,
                    candidate=candidates_by_id[item.candidate_id],
                    decision="rejected",
                    reviewed_payload=None,
                )
    except TerminalReviewBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-decisions",
    response_model=ReviewBatchDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_taxonomy_decision(
    project_workspace_id: int,
    review_batch_id: int,
    payload: TaxonomyDecisionCreate,
    session: Session = Depends(get_session),
) -> TaxonomyDecision:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    normalized_suggested_path_key = normalized_taxonomy_path_key(
        payload.suggested_top_level_category,
        payload.suggested_subcategory,
    )
    if not _batch_has_taxonomy_suggestion(
        session=session,
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch.id,
        normalized_suggested_path_key=normalized_suggested_path_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taxonomy decision suggestion must appear in the Review Batch",
        )

    resolved_taxonomy_node_id = payload.resolved_taxonomy_node_id
    if payload.decision == "mapped":
        if resolved_taxonomy_node_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mapped taxonomy decisions require a resolved taxonomy node",
            )
        _get_project_taxonomy_node_for_mapping(
            session=session,
            project_workspace_id=project_workspace_id,
            taxonomy_node_id=resolved_taxonomy_node_id,
        )
    elif payload.decision == "approved":
        if not _present(payload.suggested_subcategory):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved taxonomy decisions require a two-level category path",
            )
        resolved_taxonomy_node_id = _approve_taxonomy_path(
            session=session,
            project_workspace_id=project_workspace_id,
            top_level_category=payload.suggested_top_level_category,
            subcategory=payload.suggested_subcategory or "",
        ).id
    else:
        resolved_taxonomy_node_id = None

    taxonomy_decision = TaxonomyDecision(
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch.id,
        suggested_top_level_category=payload.suggested_top_level_category.strip(),
        suggested_subcategory=_clean(payload.suggested_subcategory),
        normalized_suggested_path_key=normalized_suggested_path_key,
        decision=payload.decision,
        resolved_taxonomy_node_id=resolved_taxonomy_node_id,
    )
    session.add(taxonomy_decision)
    session.flush()
    recalculate_review_batch_status(session=session, review_batch=review_batch)
    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-mappings",
    response_model=ReviewBatchDetail,
)
def save_review_batch_taxonomy_mapping(
    project_workspace_id: int,
    review_batch_id: int,
    payload: ReviewBatchTaxonomyMappingRequest,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    target_candidate = session.scalar(
        select(ExtractedCandidate).where(
            ExtractedCandidate.id == payload.candidate_id,
            ExtractedCandidate.review_batch_id == review_batch.id,
            ExtractedCandidate.project_workspace_id == project_workspace_id,
        )
    )
    if target_candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    candidate_suggestion = _candidate_taxonomy_suggestion(target_candidate)
    if candidate_suggestion is None and payload.apply_to_similar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apply to similar requires a complete AI taxonomy suggestion",
        )
    suggestion = candidate_suggestion or {
        "top_level_category": payload.top_level_category.strip(),
        "subcategory": payload.subcategory.strip(),
    }

    resolved_leaf = _approve_taxonomy_path(
        session=session,
        project_workspace_id=project_workspace_id,
        top_level_category=payload.top_level_category,
        subcategory=payload.subcategory,
    )
    taxonomy_decision = TaxonomyDecision(
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch.id,
        suggested_top_level_category=suggestion["top_level_category"],
        suggested_subcategory=suggestion["subcategory"],
        normalized_suggested_path_key=normalized_taxonomy_path_key(
            suggestion["top_level_category"],
            suggestion["subcategory"],
        ),
        decision="mapped",
        resolved_taxonomy_node_id=resolved_leaf.id,
    )
    session.add(taxonomy_decision)

    target_path_key = (
        normalized_taxonomy_path_key(
            suggestion["top_level_category"],
            suggestion["subcategory"],
        )
        if candidate_suggestion is not None
        else None
    )
    candidates_to_update = []
    for candidate in _get_batch_candidates(session, review_batch.id):
        candidate_suggestion = _candidate_taxonomy_suggestion(candidate)
        if not payload.apply_to_similar and candidate.id != target_candidate.id:
            continue
        if payload.apply_to_similar and (
            candidate_suggestion is None
            or normalized_taxonomy_path_key(
                candidate_suggestion["top_level_category"],
                candidate_suggestion["subcategory"],
            )
            != target_path_key
        ):
            continue
        candidates_to_update.append(candidate)

    for candidate in candidates_to_update:
        candidate.reviewed_payload = _reviewed_payload_with_category(
            candidate=candidate,
            top_level_category=payload.top_level_category,
            subcategory=payload.subcategory,
        )

    recalculate_review_batch_status(session=session, review_batch=review_batch)
    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/duplicate-groups",
    response_model=DuplicateCandidateGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_duplicate_group(
    project_workspace_id: int,
    review_batch_id: int,
    payload: DuplicateCandidateGroupCreate,
    session: Session = Depends(get_session),
) -> DuplicateCandidateGroupRead:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    _get_candidates_by_id(
        session=session,
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch.id,
        candidate_ids=payload.member_candidate_ids,
    )

    duplicate_group = DuplicateCandidateGroup(
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch.id,
    )
    session.add(duplicate_group)
    session.flush()
    for candidate_id in payload.member_candidate_ids:
        session.add(
            DuplicateCandidateGroupMember(
                duplicate_group_id=duplicate_group.id,
                candidate_id=candidate_id,
            )
        )

    session.commit()
    return _get_duplicate_group_read(session, duplicate_group.id)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/duplicate-groups/{duplicate_group_id}/members",
    response_model=DuplicateCandidateGroupRead,
)
def update_duplicate_group_members(
    project_workspace_id: int,
    review_batch_id: int,
    duplicate_group_id: int,
    payload: DuplicateCandidateGroupMembersRequest,
    session: Session = Depends(get_session),
) -> DuplicateCandidateGroupRead:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    duplicate_group = _get_duplicate_group(
        session=session,
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch.id,
        duplicate_group_id=duplicate_group_id,
    )

    if payload.add_candidate_ids:
        _get_candidates_by_id(
            session=session,
            project_workspace_id=project_workspace_id,
            review_batch_id=review_batch.id,
            candidate_ids=payload.add_candidate_ids,
        )
        existing_member_ids = set(_get_duplicate_group_member_ids(session, duplicate_group.id))
        for candidate_id in payload.add_candidate_ids:
            if candidate_id not in existing_member_ids:
                session.add(
                    DuplicateCandidateGroupMember(
                        duplicate_group_id=duplicate_group.id,
                        candidate_id=candidate_id,
                    )
                )

    if payload.remove_candidate_ids:
        for member in session.scalars(
            select(DuplicateCandidateGroupMember).where(
                DuplicateCandidateGroupMember.duplicate_group_id == duplicate_group.id,
                DuplicateCandidateGroupMember.candidate_id.in_(payload.remove_candidate_ids),
            )
        ):
            session.delete(member)

    session.commit()
    return _get_duplicate_group_read(session, duplicate_group.id)


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/close-with-no-import",
    response_model=ReviewBatchRead,
)
def close_review_batch_no_import(
    project_workspace_id: int,
    review_batch_id: int,
    session: Session = Depends(get_session),
) -> ReviewBatch:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    try:
        close_review_batch_with_no_import(session=session, review_batch=review_batch)
    except TerminalReviewBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    _mark_review_processing_job_completed(
        session=session,
        project_workspace_id=project_workspace_id,
        review_batch=review_batch,
    )
    session.commit()
    session.refresh(review_batch)
    return review_batch


@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/import",
    response_model=ImportReviewBatchResponse,
)
def import_review_batch(
    project_workspace_id: int,
    review_batch_id: int,
    session: Session = Depends(get_session),
) -> ImportReviewBatchResponse:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    if review_batch.status == "imported":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review batch already imported")
    if review_batch.status == "review_closed_no_import":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terminal review batches cannot be imported",
        )

    candidates = _get_batch_candidates(session, review_batch.id)
    if any(candidate.decision is None for candidate in candidates):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All candidates must have a review decision before import",
        )

    approved_candidates = [candidate for candidate in candidates if candidate.decision == "approved"]
    if not approved_candidates:
        if all(candidate.decision == "rejected" for candidate in candidates):
            review_batch.status = "review_closed_no_import"
            _mark_review_processing_job_completed(
                session=session,
                project_workspace_id=project_workspace_id,
                review_batch=review_batch,
            )
            session.commit()
            return ImportReviewBatchResponse(imported_purchase_lines=[])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one approved candidate is required for import",
        )
    if detect_duplicate_conflicts(session=session, review_batch=review_batch):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate conflicts must be resolved before import",
        )

    imported_purchase_lines: list[ImportedPurchaseLine] = []
    for candidate in approved_candidates:
        if candidate.reviewed_payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved candidates require reviewed payloads",
            )

        source_evidence = candidate_source_evidence(session=session, candidate=candidate)
        if source_evidence is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved candidates require source evidence",
            )

        payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
        _validate_importable_payload(payload)
        if approved_candidate_has_unresolved_taxonomy_gate(session, candidate):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved candidates require an accepted taxonomy gate",
            )
        purchase_line = _import_purchase_line(
            session=session,
            project_workspace_id=project_workspace_id,
            source_evidence=source_evidence,
            payload=payload,
        )
        _promote_merged_candidate_evidence(
            session=session,
            project_workspace_id=project_workspace_id,
            survivor_candidate=candidate,
            purchase_line=purchase_line,
        )
        imported_purchase_lines.append(ImportedPurchaseLine(id=purchase_line.id))

    review_batch.status = "imported"
    _mark_review_processing_job_completed(
        session=session,
        project_workspace_id=project_workspace_id,
        review_batch=review_batch,
    )
    session.commit()
    return ImportReviewBatchResponse(imported_purchase_lines=imported_purchase_lines)


def _get_project_review_batch(
    session: Session,
    project_workspace_id: int,
    review_batch_id: int,
) -> ReviewBatch:
    _ensure_project_workspace_exists(session, project_workspace_id)

    review_batch = session.scalar(
        select(ReviewBatch).where(
            ReviewBatch.id == review_batch_id,
            ReviewBatch.project_workspace_id == project_workspace_id,
        )
    )
    if review_batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review batch not found")
    return review_batch


def _mark_review_processing_job_completed(
    *,
    session: Session,
    project_workspace_id: int,
    review_batch: ReviewBatch,
) -> None:
    processing_job = session.scalar(
        select(ProcessingJob).where(
            ProcessingJob.project_workspace_id == project_workspace_id,
            ProcessingJob.review_batch_id == review_batch.id,
        )
    )
    if processing_job is not None:
        processing_job.status = "completed"


def _ensure_project_workspace_exists(session: Session, project_workspace_id: int) -> None:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")


def _get_batch_candidates(session: Session, review_batch_id: int) -> list[ExtractedCandidate]:
    return list(
        session.scalars(
            select(ExtractedCandidate)
            .where(ExtractedCandidate.review_batch_id == review_batch_id)
            .order_by(ExtractedCandidate.id)
        )
    )


def _review_batch_detail(session: Session, review_batch: ReviewBatch) -> ReviewBatchDetail:
    candidates = _get_batch_candidates(session, review_batch.id)
    return ReviewBatchDetail(
        review_batch=review_batch,
        candidates=[_candidate_read(session, candidate) for candidate in candidates],
        duplicate_groups=_get_duplicate_group_reads(session, review_batch.id),
        duplicate_conflicts=detect_duplicate_conflicts(
            session=session,
            review_batch=review_batch,
        ),
        taxonomy_decisions=[
            _taxonomy_decision_read(session, decision)
            for decision in session.scalars(
                select(TaxonomyDecision)
                .where(TaxonomyDecision.review_batch_id == review_batch.id)
                .order_by(TaxonomyDecision.id)
            )
        ],
    )


def _batch_has_taxonomy_suggestion(
    *,
    session: Session,
    project_workspace_id: int,
    review_batch_id: int,
    normalized_suggested_path_key: str,
) -> bool:
    for candidate in _get_batch_candidates(session, review_batch_id):
        if candidate.project_workspace_id != project_workspace_id:
            continue
        for _, _, suggestion in _candidate_taxonomy_subjects(candidate):
            top_level_category = suggestion.get("top_level_category")
            subcategory = suggestion.get("subcategory")
            if not isinstance(top_level_category, str) or not _present(top_level_category):
                continue
            candidate_path_key = normalized_taxonomy_path_key(
                top_level_category,
                subcategory if isinstance(subcategory, str) else None,
            )
            if candidate_path_key == normalized_suggested_path_key:
                return True
    return False


def _candidate_taxonomy_suggestion(candidate: ExtractedCandidate) -> dict[str, str] | None:
    suggestion = candidate.proposed_payload.get("category_suggestion")
    if not isinstance(suggestion, dict):
        return None
    top_level_category = suggestion.get("top_level_category")
    subcategory = suggestion.get("subcategory")
    if not isinstance(top_level_category, str) or not _present(top_level_category):
        return None
    if not isinstance(subcategory, str) or not _present(subcategory):
        return None
    return {
        "top_level_category": top_level_category.strip(),
        "subcategory": subcategory.strip(),
    }


def _reviewed_payload_with_category(
    *,
    candidate: ExtractedCandidate,
    top_level_category: str,
    subcategory: str,
) -> dict:
    payload = {
        **candidate.proposed_payload,
        **(candidate.reviewed_payload or {}),
        "top_level_category": top_level_category.strip(),
        "subcategory": subcategory.strip(),
    }
    payload.pop("category_suggestion", None)
    payload.pop("confidence", None)
    payload.pop("currency_state", None)
    payload.pop("evidence", None)
    return ReviewedPurchaseLinePayload.model_validate(payload).model_dump(mode="json")


def _candidate_read(session: Session, candidate: ExtractedCandidate) -> ExtractedCandidateRead:
    candidate_read = ExtractedCandidateRead.model_validate(candidate)
    source_file = session.scalar(
        select(SourceFile).where(
            SourceFile.source_submission_id == candidate.source_submission_id,
            SourceFile.project_workspace_id == candidate.project_workspace_id,
        )
    )
    source_file_summary = (
        SourceFileSummary(
            id=source_file.id,
            original_filename=source_file.original_filename,
            byte_size=source_file.byte_size,
            declared_mime_type=source_file.declared_mime_type,
            uploaded_at=source_file.uploaded_at,
            sha256_checksum=source_file.sha256_checksum,
        )
        if source_file is not None
        else None
    )
    return candidate_read.model_copy(
        update={
            "source_file": source_file_summary,
            "taxonomy_gate": _taxonomy_gate_for_candidate(session, candidate),
            "taxonomy_gates": _taxonomy_gates_for_candidate(session, candidate),
            "existing_memory_matches": _existing_memory_matches(session, candidate),
            "taxonomy_default": _taxonomy_default_for_candidate(session, candidate),
        }
    )


def _get_candidates_by_id(
    *,
    session: Session,
    project_workspace_id: int,
    review_batch_id: int,
    candidate_ids: list[int],
) -> list[ExtractedCandidate]:
    candidates = list(
        session.scalars(
            select(ExtractedCandidate).where(
                ExtractedCandidate.id.in_(candidate_ids),
                ExtractedCandidate.project_workspace_id == project_workspace_id,
                ExtractedCandidate.review_batch_id == review_batch_id,
            )
        )
    )
    if len(candidates) != len(set(candidate_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidates


def _get_duplicate_group(
    *,
    session: Session,
    project_workspace_id: int,
    review_batch_id: int,
    duplicate_group_id: int,
) -> DuplicateCandidateGroup:
    duplicate_group = session.scalar(
        select(DuplicateCandidateGroup).where(
            DuplicateCandidateGroup.id == duplicate_group_id,
            DuplicateCandidateGroup.project_workspace_id == project_workspace_id,
            DuplicateCandidateGroup.review_batch_id == review_batch_id,
        )
    )
    if duplicate_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duplicate group not found")
    return duplicate_group


def _get_duplicate_group_reads(
    session: Session,
    review_batch_id: int,
) -> list[DuplicateCandidateGroupRead]:
    groups = session.scalars(
        select(DuplicateCandidateGroup)
        .where(DuplicateCandidateGroup.review_batch_id == review_batch_id)
        .order_by(DuplicateCandidateGroup.id)
    )
    return [_duplicate_group_read(session, group) for group in groups]


def _get_duplicate_group_read(
    session: Session,
    duplicate_group_id: int,
) -> DuplicateCandidateGroupRead:
    duplicate_group = session.get(DuplicateCandidateGroup, duplicate_group_id)
    if duplicate_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duplicate group not found")
    return _duplicate_group_read(session, duplicate_group)


def _duplicate_group_read(
    session: Session,
    duplicate_group: DuplicateCandidateGroup,
) -> DuplicateCandidateGroupRead:
    return DuplicateCandidateGroupRead(
        id=duplicate_group.id,
        project_workspace_id=duplicate_group.project_workspace_id,
        review_batch_id=duplicate_group.review_batch_id,
        member_candidate_ids=_get_duplicate_group_member_ids(session, duplicate_group.id),
    )


def _get_duplicate_group_member_ids(
    session: Session,
    duplicate_group_id: int,
) -> list[int]:
    return list(
        session.scalars(
            select(DuplicateCandidateGroupMember.candidate_id)
            .where(DuplicateCandidateGroupMember.duplicate_group_id == duplicate_group_id)
            .order_by(DuplicateCandidateGroupMember.id)
        )
    )


def _ensure_review_batch_editable_or_conflict(review_batch: ReviewBatch) -> None:
    if review_batch.status in {"imported", "review_closed_no_import"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terminal review batches cannot be changed",
        )


def _validate_importable_payload(payload: ReviewedPurchaseLinePayload) -> None:
    concepts = payload.concepts()
    concept_types = {concept.concept_type for concept in concepts}
    if len(concepts) not in {1, 2} or len(concept_types) != len(concepts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved candidates require one Material or Service, or one of each",
        )
    if len(concepts) == 2 and concept_types != {"material", "service"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bundled Purchase Lines require exactly one Material and one Service",
        )
    for concept in concepts:
        if not _present(concept.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved candidates require a linked concept name",
            )
        if not _present(concept.top_level_category) or not _present(concept.subcategory):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each linked concept requires a resolved category path",
            )
    if payload.provider_state == "external":
        if not _present(payload.provider_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="External Provider State requires a Provider name",
            )
        if not _present(payload.provider_top_level_category) or not _present(
            payload.provider_subcategory
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="External Providers require their own resolved category path",
            )
    if payload.provider_state == "unknown" and any(
        _present(value)
        for value in (
            payload.provider_name,
            payload.provider_top_level_category,
            payload.provider_subcategory,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown Provider State cannot include Provider details",
        )


def _import_purchase_line(
    *,
    session: Session,
    project_workspace_id: int,
    source_evidence: CandidateSourceEvidence,
    payload: ReviewedPurchaseLinePayload,
) -> PurchaseLine:
    concept_records: list[tuple[str, MemoryRecord]] = []
    for concept in payload.concepts():
        top_level = _get_or_create_taxonomy_node(
            session=session,
            project_workspace_id=project_workspace_id,
            name=concept.top_level_category or "",
            parent_id=None,
        )
        subcategory = _get_or_create_taxonomy_node(
            session=session,
            project_workspace_id=project_workspace_id,
            name=concept.subcategory or "",
            parent_id=top_level.id,
        )
        concept_record = _get_or_create_entity_record(
            session=session,
            project_workspace_id=project_workspace_id,
            record_type=concept.concept_type,
            display_name=concept.name or "",
            taxonomy_node_id=subcategory.id,
        )
        _ensure_type_record(
            session,
            Material if concept.concept_type == "material" else Service,
            concept_record.id,
        )
        concept_records.append((concept.concept_type, concept_record))

    provider_record = None
    provider_state = _resolved_provider_state(
        session=session,
        project_workspace_id=project_workspace_id,
        payload=payload,
    )
    provider_name = _clean(payload.provider_name) if provider_state == "external" else None
    if provider_state == "external" and provider_name is not None:
        provider_top_level_name = payload.provider_top_level_category or "Providers"
        provider_subcategory_name = payload.provider_subcategory or "General"
        provider_top_level = _get_or_create_taxonomy_node(
            session=session,
            project_workspace_id=project_workspace_id,
            name=provider_top_level_name,
            parent_id=None,
        )
        provider_subcategory = _get_or_create_taxonomy_node(
            session=session,
            project_workspace_id=project_workspace_id,
            name=provider_subcategory_name,
            parent_id=provider_top_level.id,
        )
        provider_record = _get_or_create_entity_record(
            session=session,
            project_workspace_id=project_workspace_id,
            record_type="provider",
            display_name=provider_name,
            taxonomy_node_id=provider_subcategory.id,
        )
        _ensure_type_record(session, Provider, provider_record.id)

    primary_record = concept_records[0][1]
    purchase_display_name = " + ".join(record.display_name for _, record in concept_records)
    purchase_record = MemoryRecord(
        project_workspace_id=project_workspace_id,
        record_type="purchase_line",
        display_name=purchase_display_name,
        normalized_name=_normalize(purchase_display_name),
        taxonomy_node_id=primary_record.taxonomy_node_id,
        status="active",
    )
    session.add(purchase_record)
    session.flush()

    evidence = EvidenceRecord(
        project_workspace_id=project_workspace_id,
        manual_source_entry_id=source_evidence.manual_source_entry_id,
        source_file_id=source_evidence.source_file_id,
        source_label=source_evidence.source_label,
        content=source_evidence.content,
    )
    session.add(evidence)
    session.flush()

    evidence_record_ids = [record.id for _, record in concept_records]
    if provider_record is not None:
        evidence_record_ids.append(provider_record.id)
    for record_id in [purchase_record.id, *evidence_record_ids]:
        if record_id is not None:
            session.add(
                MemoryRecordEvidenceLink(
                    memory_record_id=record_id,
                    evidence_record_id=evidence.id,
                )
            )

    annotation_targets = {
        "purchase_line": purchase_record,
        **{concept_type: record for concept_type, record in concept_records},
    }
    if provider_record is not None:
        annotation_targets["provider"] = provider_record
    for annotation in payload.annotation_proposals:
        target_record = annotation_targets.get(annotation.target)
        if target_record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Annotation target must be present on the imported candidate",
            )
        session.add(
            EvidenceAnnotation(
                evidence_record_id=evidence.id,
                memory_record_id=target_record.id,
                annotation_type=annotation.annotation_type,
                text=annotation.text.strip(),
                proposal_id=annotation.proposal_id,
                source_excerpt=annotation.source_excerpt,
                source_locator=annotation.source_locator,
                provenance=annotation.provenance,
            )
        )

    remarks_or_terms = _clean(payload.remarks_or_terms)
    if remarks_or_terms is not None and not payload.annotation_proposals:
        session.add(
            EvidenceAnnotation(
                evidence_record_id=evidence.id,
                memory_record_id=purchase_record.id,
                annotation_type="general_qualifier",
                text=remarks_or_terms,
                proposal_id="legacy:remarks_or_terms",
                source_excerpt=remarks_or_terms,
                source_locator={
                    "kind": "structured_field",
                    "field_path": "structured_payload.remarks_or_terms",
                },
                provenance="legacy_default",
            )
        )

    price = _clean(payload.price)
    currency = _clean(payload.currency) if price is not None else None
    purchase_line = PurchaseLine(
        project_workspace_id=project_workspace_id,
        memory_record_id=purchase_record.id,
        provider_memory_record_id=provider_record.id if provider_record else None,
        provider_state=provider_state,
        quantity=_clean(payload.quantity),
        unit=_clean(payload.unit),
        unit_state="known" if _present(payload.unit) else "unknown",
        price=price,
        currency=currency or ("PHP" if price is not None else None),
        price_state="known" if price is not None else "unknown",
        purchase_date=payload.purchase_date,
        date_state="known" if payload.purchase_date is not None else "unknown",
    )
    session.add(purchase_line)
    session.flush()
    for concept_type, concept_record in concept_records:
        session.add(
            PurchaseLineConceptLink(
                purchase_line_id=purchase_line.id,
                concept_memory_record_id=concept_record.id,
                concept_type=concept_type,
            )
        )
    session.flush()
    return purchase_line


def _resolved_provider_state(
    *,
    session: Session,
    project_workspace_id: int,
    payload: ReviewedPurchaseLinePayload,
) -> str:
    if payload.provider_state is not None:
        return payload.provider_state
    provider_name = _clean(payload.provider_name)
    if provider_name is None:
        return "unknown"
    project = session.get(ProjectWorkspace, project_workspace_id)
    contractor = _normalize(project.contractor_assigned) if project is not None else "internal"
    if contractor != "internal" and _normalize(provider_name) == contractor:
        return "internal"
    return "external"


def _promote_merged_candidate_evidence(
    *,
    session: Session,
    project_workspace_id: int,
    survivor_candidate: ExtractedCandidate,
    purchase_line: PurchaseLine,
) -> None:
    merged_candidates = session.scalars(
        select(ExtractedCandidate)
        .where(
            ExtractedCandidate.review_batch_id == survivor_candidate.review_batch_id,
            ExtractedCandidate.decision == "merged",
            ExtractedCandidate.merged_into_candidate_id == survivor_candidate.id,
        )
        .order_by(ExtractedCandidate.id)
    )
    for merged_candidate in merged_candidates:
        source_evidence = candidate_source_evidence(
            session=session, candidate=merged_candidate
        )
        if source_evidence is None:
            continue

        evidence = EvidenceRecord(
            project_workspace_id=project_workspace_id,
            manual_source_entry_id=source_evidence.manual_source_entry_id,
            source_file_id=source_evidence.source_file_id,
            source_label=source_evidence.source_label,
            content=source_evidence.content,
        )
        session.add(evidence)
        session.flush()

        record_ids = [purchase_line.memory_record_id, purchase_line.provider_memory_record_id]
        record_ids.extend(
            session.scalars(
                select(PurchaseLineConceptLink.concept_memory_record_id).where(
                    PurchaseLineConceptLink.purchase_line_id == purchase_line.id
                )
            )
        )
        for record_id in record_ids:
            if record_id is not None:
                session.add(
                    MemoryRecordEvidenceLink(
                        memory_record_id=record_id,
                        evidence_record_id=evidence.id,
                    )
                )

        merged_payload_data = (
            merged_candidate.reviewed_payload or merged_candidate.proposed_payload
        )
        try:
            merged_payload = ReviewedPurchaseLinePayload.model_validate(merged_payload_data)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Merged candidate annotations require a valid reviewed payload",
            ) from error

        target_records = {
            record.record_type: record
            for record in session.scalars(
                select(MemoryRecord).where(MemoryRecord.id.in_(record_ids))
            )
            if record is not None
        }
        for annotation in merged_payload.annotation_proposals:
            target_record = target_records.get(annotation.target)
            if target_record is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Merged annotation target must be present on the surviving candidate"
                    ),
                )
            session.add(
                EvidenceAnnotation(
                    evidence_record_id=evidence.id,
                    memory_record_id=target_record.id,
                    annotation_type=annotation.annotation_type,
                    text=annotation.text.strip(),
                    proposal_id=annotation.proposal_id,
                    source_excerpt=annotation.source_excerpt,
                    source_locator=annotation.source_locator,
                    provenance=annotation.provenance,
                )
            )


def _get_or_create_taxonomy_node(
    *,
    session: Session,
    project_workspace_id: int,
    name: str,
    parent_id: int | None,
) -> TaxonomyNode:
    cleaned_name = name.strip()
    normalized_name = normalize_taxonomy_name(cleaned_name)
    taxonomy_node = session.scalar(
        select(TaxonomyNode).where(
            TaxonomyNode.project_workspace_id == project_workspace_id,
            TaxonomyNode.parent_id == parent_id,
            TaxonomyNode.normalized_name == normalized_name,
        )
    )
    if taxonomy_node is not None:
        return taxonomy_node
    _ensure_unique_taxonomy_sibling_name(
        session=session,
        project_workspace_id=project_workspace_id,
        parent_id=parent_id,
        normalized_name=normalized_name,
    )

    taxonomy_node = TaxonomyNode(
        project_workspace_id=project_workspace_id,
        parent_id=parent_id,
        name=cleaned_name,
        normalized_name=normalized_name,
    )
    session.add(taxonomy_node)
    session.flush()
    return taxonomy_node


def _ensure_unique_taxonomy_sibling_name(
    *,
    session: Session,
    project_workspace_id: int,
    parent_id: int | None,
    normalized_name: str,
    exclude_taxonomy_node_id: int | None = None,
) -> None:
    query = select(TaxonomyNode).where(
        TaxonomyNode.project_workspace_id == project_workspace_id,
        TaxonomyNode.parent_id == parent_id,
        TaxonomyNode.normalized_name == normalized_name,
    )
    if exclude_taxonomy_node_id is not None:
        query = query.where(TaxonomyNode.id != exclude_taxonomy_node_id)
    if session.scalar(query) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taxonomy node names must be unique among siblings",
        )


def _get_project_taxonomy_node_for_mapping(
    *,
    session: Session,
    project_workspace_id: int,
    taxonomy_node_id: int,
) -> TaxonomyNode:
    taxonomy_node = session.get(TaxonomyNode, taxonomy_node_id)
    if taxonomy_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy node not found")
    if taxonomy_node.project_workspace_id != project_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapped taxonomy node must belong to the selected Project Workspace",
        )
    if taxonomy_node.parent_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapped taxonomy decisions require a subcategory leaf node",
        )
    return taxonomy_node


def _approve_taxonomy_path(
    *,
    session: Session,
    project_workspace_id: int,
    top_level_category: str,
    subcategory: str,
) -> TaxonomyNode:
    top_level = _get_or_create_taxonomy_node(
        session=session,
        project_workspace_id=project_workspace_id,
        name=top_level_category,
        parent_id=None,
    )
    return _get_or_create_taxonomy_node(
        session=session,
        project_workspace_id=project_workspace_id,
        name=subcategory,
        parent_id=top_level.id,
    )


def _get_or_create_entity_record(
    *,
    session: Session,
    project_workspace_id: int,
    record_type: str,
    display_name: str,
    taxonomy_node_id: int,
) -> MemoryRecord:
    normalized_name = _normalize(display_name)
    memory_record = session.scalar(
        select(MemoryRecord).where(
            MemoryRecord.project_workspace_id == project_workspace_id,
            MemoryRecord.record_type == record_type,
            MemoryRecord.normalized_name == normalized_name,
            MemoryRecord.status == "active",
        )
    )
    if memory_record is not None:
        return memory_record

    memory_record = MemoryRecord(
        project_workspace_id=project_workspace_id,
        record_type=record_type,
        display_name=display_name.strip(),
        normalized_name=normalized_name,
        taxonomy_node_id=taxonomy_node_id,
        status="active",
    )
    session.add(memory_record)
    session.flush()
    return memory_record


def _ensure_type_record(session: Session, model: type[Material] | type[Service] | type[Provider], memory_record_id: int) -> None:
    existing = session.scalar(select(model).where(model.memory_record_id == memory_record_id))
    if existing is None:
        session.add(model(memory_record_id=memory_record_id))
        session.flush()


def _present(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _taxonomy_gate_for_candidate(
    session: Session,
    candidate: ExtractedCandidate,
) -> TaxonomyGateRead | None:
    if _candidate_reviewed_category_path(candidate) is not None:
        return None
    subjects = _candidate_taxonomy_subjects(candidate)
    if len(subjects) != 1 or candidate.proposed_payload.get("linked_concepts"):
        return None
    return _taxonomy_gate_for_suggestion(session, candidate, subjects[0][2])


def _taxonomy_gates_for_candidate(
    session: Session,
    candidate: ExtractedCandidate,
) -> list[CandidateTaxonomyGateRead]:
    _ensure_candidate_taxonomy_gates(session, candidate)
    persisted_gates = list(
        session.scalars(
            select(TaxonomyGate)
            .where(
                TaxonomyGate.candidate_id == candidate.id,
                TaxonomyGate.active.is_(True),
            )
            .order_by(TaxonomyGate.id)
        )
    )
    if persisted_gates:
        return [_persisted_taxonomy_gate_read(session, gate) for gate in persisted_gates]

    reviewed_subjects = _reviewed_taxonomy_subjects(candidate)
    gates: list[CandidateTaxonomyGateRead] = []
    for subject_type, subject_name, suggestion in _candidate_taxonomy_subjects(candidate):
        reviewed_subject = reviewed_subjects.get(subject_type)
        if reviewed_subject is not None:
            subject_name, reviewed_path_key = reviewed_subject
            suggestion_path_key = normalized_taxonomy_path_key(
                str(suggestion.get("top_level_category") or ""),
                suggestion.get("subcategory")
                if isinstance(suggestion.get("subcategory"), str)
                else None,
            )
            if reviewed_path_key != suggestion_path_key:
                continue
        if _existing_memory_record(
            session,
            candidate.project_workspace_id,
            subject_type,
            subject_name,
        ) is not None:
            continue
        gate = _taxonomy_gate_for_suggestion(session, candidate, suggestion)
        if gate is not None:
            gates.append(
                CandidateTaxonomyGateRead(
                    subject_type=subject_type,
                    subject_name=subject_name,
                    **gate.model_dump(),
                )
            )
    return gates


def _ensure_candidate_taxonomy_gates(
    session: Session,
    candidate: ExtractedCandidate,
) -> None:
    existing_gates = {
        gate.subject_type: gate
        for gate in session.scalars(
            select(TaxonomyGate).where(TaxonomyGate.candidate_id == candidate.id)
        )
    }
    relevant_subject_types: set[str] = set()
    for subject_type, subject_name, suggestion in _active_candidate_taxonomy_subjects(candidate):
        relevant_subject_types.add(subject_type)
        existing_gate = existing_gates.get(subject_type)
        if existing_gate is not None:
            existing_gate.active = True
            existing_gate.subject_name = subject_name
            existing_gate.normalized_subject_name = _normalize(subject_name)
            suggestion_top_level = suggestion.get("top_level_category")
            suggestion_subcategory = suggestion.get("subcategory")
            if (
                existing_gate.original_subcategory is None
                and isinstance(suggestion_top_level, str)
                and _present(suggestion_top_level)
                and isinstance(suggestion_subcategory, str)
                and _present(suggestion_subcategory)
            ):
                existing_gate.original_top_level_category = suggestion_top_level.strip()
                existing_gate.original_subcategory = suggestion_subcategory.strip()
                existing_gate.normalized_original_path_key = normalized_taxonomy_path_key(
                    suggestion_top_level, suggestion_subcategory
                )
            continue
        top_level_category = suggestion.get("top_level_category")
        subcategory = suggestion.get("subcategory")
        if not isinstance(top_level_category, str) or not _present(top_level_category):
            continue
        session.add(
            TaxonomyGate(
                project_workspace_id=candidate.project_workspace_id,
                review_batch_id=candidate.review_batch_id,
                candidate_id=candidate.id,
                subject_type=subject_type,
                subject_name=subject_name,
                normalized_subject_name=_normalize(subject_name),
                original_top_level_category=top_level_category.strip(),
                original_subcategory=(
                    subcategory.strip()
                    if isinstance(subcategory, str) and _present(subcategory)
                    else None
                ),
                normalized_original_path_key=normalized_taxonomy_path_key(
                    top_level_category,
                    subcategory if isinstance(subcategory, str) else None,
                ),
                selected_proposal="ai_suggestion",
                status="needs_decision",
                active=True,
            )
        )
    for subject_type, existing_gate in existing_gates.items():
        if subject_type not in relevant_subject_types:
            existing_gate.active = False
    session.flush()


def _active_candidate_taxonomy_subjects(
    candidate: ExtractedCandidate,
) -> list[tuple[str, str, dict]]:
    proposed_subjects = {
        subject_type: (subject_name, suggestion)
        for subject_type, subject_name, suggestion in _candidate_taxonomy_subjects(candidate)
    }
    if candidate.decision != "approved" or candidate.reviewed_payload is None:
        return [
            (subject_type, subject_name, suggestion)
            for subject_type, (subject_name, suggestion) in proposed_subjects.items()
        ]

    payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
    subjects: list[tuple[str, str, dict]] = []
    for concept in payload.concepts():
        if not _present(concept.name):
            continue
        proposed = proposed_subjects.get(concept.concept_type)
        suggestion = (
            proposed[1]
            if proposed is not None
            else {
                "top_level_category": concept.top_level_category,
                "subcategory": concept.subcategory,
            }
        )
        subjects.append((concept.concept_type, concept.name or "", suggestion))
    if payload.provider_state == "external" and _present(payload.provider_name):
        proposed = proposed_subjects.get("provider")
        suggestion = (
            proposed[1]
            if proposed is not None
            else {
                "top_level_category": payload.provider_top_level_category,
                "subcategory": payload.provider_subcategory,
            }
        )
        subjects.append(("provider", payload.provider_name or "", suggestion))
    return subjects


def _apply_accepted_gate_category(
    *,
    session: Session,
    taxonomy_gate: TaxonomyGate,
    top_level_category: str,
    subcategory: str,
) -> None:
    candidate = session.get(ExtractedCandidate, taxonomy_gate.candidate_id)
    if candidate is None or candidate.reviewed_payload is None:
        return
    payload = {**candidate.reviewed_payload}
    if taxonomy_gate.subject_type in {"material", "service"}:
        linked_concepts = payload.get("linked_concepts")
        if isinstance(linked_concepts, list) and linked_concepts:
            payload["linked_concepts"] = [
                {
                    **concept,
                    **(
                        {
                            "top_level_category": top_level_category.strip(),
                            "subcategory": subcategory.strip(),
                        }
                        if isinstance(concept, dict)
                        and concept.get("concept_type") == taxonomy_gate.subject_type
                        else {}
                    ),
                }
                if isinstance(concept, dict)
                else concept
                for concept in linked_concepts
            ]
        elif payload.get("line_type") == taxonomy_gate.subject_type:
            payload["top_level_category"] = top_level_category.strip()
            payload["subcategory"] = subcategory.strip()
    elif taxonomy_gate.subject_type == "provider":
        payload["provider_top_level_category"] = top_level_category.strip()
        payload["provider_subcategory"] = subcategory.strip()
    candidate.reviewed_payload = ReviewedPurchaseLinePayload.model_validate(payload).model_dump(
        mode="json"
    )


def _persisted_taxonomy_gate_read(
    session: Session,
    gate: TaxonomyGate,
) -> CandidateTaxonomyGateRead:
    original_path = _display_taxonomy_path(
        gate.original_top_level_category, gate.original_subcategory
    )
    reviewer_draft_path = (
        _display_taxonomy_path(
            gate.reviewer_draft_top_level_category,
            gate.reviewer_draft_subcategory,
        )
        if _present(gate.reviewer_draft_top_level_category)
        else None
    )
    selected_path = (
        reviewer_draft_path
        if gate.selected_proposal == "reviewer_draft" and reviewer_draft_path is not None
        else original_path
    )
    history = list(
        session.scalars(
            select(TaxonomyDecision)
            .where(TaxonomyDecision.taxonomy_gate_id == gate.id)
            .order_by(TaxonomyDecision.id)
        )
    )
    active_decision = next((decision for decision in reversed(history) if not decision.superseded), None)
    accepted_path = (
        _taxonomy_node_path(session, active_decision.resolved_taxonomy_node_id)
        if active_decision is not None and active_decision.resolved_taxonomy_node_id is not None
        else None
    )
    return CandidateTaxonomyGateRead(
        id=gate.id,
        active=gate.active,
        subject_type=gate.subject_type,
        subject_name=gate.subject_name,
        status=gate.status,
        reason="candidate_acceptance_required" if gate.status == "needs_decision" else None,
        suggested_category_path=original_path,
        original_ai_category_path=original_path,
        reviewer_draft_category_path=reviewer_draft_path,
        selected_proposal=gate.selected_proposal,
        selected_category_path=selected_path,
        resolved_category_path=accepted_path,
        accepted_category_path=accepted_path,
        decision=active_decision.decision if active_decision is not None else None,
        taxonomy_decision_id=active_decision.id if active_decision is not None else None,
        accepted_source=active_decision.accepted_source if active_decision is not None else None,
        decision_history=[_taxonomy_decision_read(session, item) for item in history],
    )


def _taxonomy_decision_read(
    session: Session,
    decision: TaxonomyDecision,
) -> TaxonomyDecisionRead:
    return TaxonomyDecisionRead.model_validate(decision).model_copy(
        update={
            "accepted_category_path": (
                _taxonomy_node_path(session, decision.resolved_taxonomy_node_id)
                if decision.resolved_taxonomy_node_id is not None
                else None
            )
        }
    )


def _existing_memory_matches(
    session: Session,
    candidate: ExtractedCandidate,
) -> list[ExistingMemoryMatchRead]:
    matches: list[ExistingMemoryMatchRead] = []
    seen: set[tuple[str, int]] = set()
    for subject_type, subject_name, _suggestion in _candidate_taxonomy_subjects(candidate):
        record = _existing_memory_record(
            session,
            candidate.project_workspace_id,
            subject_type,
            subject_name,
        )
        if record is None or (subject_type, record.id) in seen:
            continue
        seen.add((subject_type, record.id))
        category_path = _taxonomy_node_path(session, record.taxonomy_node_id)
        if category_path is None:
            continue
        matches.append(
            ExistingMemoryMatchRead(
                subject_type=subject_type,
                subject_name=record.display_name,
                category_path=category_path,
            )
        )
    return matches


def _existing_memory_record(
    session: Session,
    project_workspace_id: int,
    subject_type: str,
    subject_name: str,
) -> MemoryRecord | None:
    return session.scalar(
        select(MemoryRecord).where(
            MemoryRecord.project_workspace_id == project_workspace_id,
            MemoryRecord.record_type == subject_type,
            MemoryRecord.normalized_name == _normalize(subject_name),
            MemoryRecord.status == "active",
        )
    )


def _candidate_taxonomy_subjects(
    candidate: ExtractedCandidate,
) -> list[tuple[str, str, dict]]:
    subjects: list[tuple[str, str, dict]] = []
    linked_concepts = candidate.proposed_payload.get("linked_concepts")
    if isinstance(linked_concepts, list):
        for concept in linked_concepts:
            if not isinstance(concept, dict):
                continue
            concept_type = concept.get("concept_type")
            name = concept.get("name")
            suggestion = concept.get("category_suggestion")
            if (
                concept_type in {"material", "service"}
                and isinstance(name, str)
                and _present(name)
                and isinstance(suggestion, dict)
            ):
                subjects.append((concept_type, name.strip(), suggestion))
        if candidate.proposed_payload.get("provider_state") == "external":
            provider_name = candidate.proposed_payload.get("provider_name")
            provider_suggestion = candidate.proposed_payload.get(
                "provider_category_suggestion"
            )
            if (
                isinstance(provider_name, str)
                and _present(provider_name)
                and isinstance(provider_suggestion, dict)
            ):
                subjects.append(("provider", provider_name.strip(), provider_suggestion))
        return subjects

    suggestion = candidate.proposed_payload.get("category_suggestion")
    line_type = candidate.proposed_payload.get("line_type")
    name = candidate.proposed_payload.get("name")
    if (
        line_type in {"material", "service"}
        and isinstance(name, str)
        and _present(name)
        and isinstance(suggestion, dict)
    ):
        subjects.append((line_type, name.strip(), suggestion))
    return subjects


def _reviewed_taxonomy_subjects(candidate: ExtractedCandidate) -> dict[str, tuple[str, str]]:
    if candidate.reviewed_payload is None:
        return {}
    payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
    subjects = {
        concept.concept_type: (
            concept.name or "",
            normalized_taxonomy_path_key(
                concept.top_level_category or "",
                concept.subcategory,
            ),
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
            normalized_taxonomy_path_key(
                payload.provider_top_level_category or "",
                payload.provider_subcategory,
            ),
        )
    return subjects


def _taxonomy_gate_for_suggestion(
    session: Session,
    candidate: ExtractedCandidate,
    suggestion: dict,
) -> TaxonomyGateRead | None:

    top_level_category = suggestion.get("top_level_category")
    subcategory = suggestion.get("subcategory")
    if not isinstance(top_level_category, str) or not _present(top_level_category):
        return None

    suggested_category_path = _display_taxonomy_path(top_level_category, subcategory)
    path_key = normalized_taxonomy_path_key(
        top_level_category,
        subcategory if isinstance(subcategory, str) else None,
    )
    decision = latest_taxonomy_decision_for_path(
        session=session,
        project_workspace_id=candidate.project_workspace_id,
        normalized_path_key=path_key,
    )
    if decision is not None:
        resolved_category_path = (
            _taxonomy_node_path(session, decision.resolved_taxonomy_node_id)
            if decision.resolved_taxonomy_node_id is not None
            else None
        )
        if decision.decision in {"approved", "mapped"}:
            status_by_decision = {
                "approved": "resolved_by_approval",
                "mapped": "resolved_by_mapping",
            }
            reason_by_decision = {
                "approved": "approved_taxonomy_decision",
                "mapped": "mapped_taxonomy_decision",
            }
            return TaxonomyGateRead(
                status=status_by_decision[decision.decision],
                reason=reason_by_decision[decision.decision],
                suggested_category_path=suggested_category_path,
                resolved_category_path=resolved_category_path,
                decision=decision.decision,
                taxonomy_decision_id=decision.id,
            )
        prior_rejection = {
            "taxonomy_decision_id": decision.id,
            "suggested_category_path": suggested_category_path,
        }
    else:
        prior_rejection = None

    if not isinstance(subcategory, str) or not _present(subcategory):
        return TaxonomyGateRead(
            status="subcategory_required",
            reason="subcategory_required",
            suggested_category_path=suggested_category_path,
            prior_rejection=prior_rejection,
        )

    if prior_rejection is not None:
        return TaxonomyGateRead(
            status="new_taxonomy_path",
            reason="new_taxonomy_path",
            suggested_category_path=suggested_category_path,
            prior_rejection=prior_rejection,
        )

    if taxonomy_leaf_node_for_path(
        session=session,
        project_workspace_id=candidate.project_workspace_id,
        top_level_category=top_level_category,
        subcategory=subcategory,
    ) is None:
        return TaxonomyGateRead(
            status="new_taxonomy_path",
            reason="new_taxonomy_path",
            suggested_category_path=suggested_category_path,
            prior_rejection=prior_rejection,
        )
    return None


def _taxonomy_default_for_candidate(
    session: Session,
    candidate: ExtractedCandidate,
) -> TaxonomyDefaultRead | None:
    if candidate.reviewed_payload is not None:
        return None

    review_batch = session.get(ReviewBatch, candidate.review_batch_id)
    if review_batch is not None and review_batch.status in {"imported", "review_closed_no_import"}:
        return None

    suggestion = candidate.proposed_payload.get("category_suggestion")
    if not isinstance(suggestion, dict):
        return None

    top_level_category = suggestion.get("top_level_category")
    subcategory = suggestion.get("subcategory")
    if (
        not isinstance(top_level_category, str)
        or not _present(top_level_category)
        or not isinstance(subcategory, str)
        or not _present(subcategory)
    ):
        return None

    decision = latest_taxonomy_decision_for_path(
        session=session,
        project_workspace_id=candidate.project_workspace_id,
        normalized_path_key=normalized_taxonomy_path_key(top_level_category, subcategory),
    )
    if decision is None or decision.decision not in {"approved", "mapped"}:
        return None
    if decision.resolved_taxonomy_node_id is None:
        return None

    resolved_category_path = _taxonomy_node_path(session, decision.resolved_taxonomy_node_id)
    if resolved_category_path is None:
        return None

    suggested_category_path = _display_taxonomy_path(
        decision.suggested_top_level_category,
        decision.suggested_subcategory,
    )
    source = (
        "approved_taxonomy_decision"
        if decision.decision == "approved"
        else "mapped_taxonomy_decision"
    )
    provenance_text = (
        f"Defaulted from a previous approved taxonomy decision: {resolved_category_path}"
        if decision.decision == "approved"
        else f"Defaulted from a previous mapping: {suggested_category_path} -> {resolved_category_path}"
    )
    return TaxonomyDefaultRead(
        resolved_category_path=resolved_category_path,
        source=source,
        provenance_text=provenance_text,
        taxonomy_decision_id=decision.id,
    )


def _display_taxonomy_path(top_level_category: str, subcategory: object) -> str:
    if isinstance(subcategory, str) and _present(subcategory):
        return f"{top_level_category.strip()} / {subcategory.strip()}"
    return top_level_category.strip()


def _taxonomy_node_path(session: Session, taxonomy_node_id: int) -> str | None:
    taxonomy_node = session.get(TaxonomyNode, taxonomy_node_id)
    if taxonomy_node is None:
        return None
    if taxonomy_node.parent_id is None:
        return taxonomy_node.name
    parent = session.get(TaxonomyNode, taxonomy_node.parent_id)
    if parent is None:
        return taxonomy_node.name
    return f"{parent.name} / {taxonomy_node.name}"


def _candidate_reviewed_category_path(candidate: ExtractedCandidate) -> str | None:
    if candidate.reviewed_payload is None:
        return None

    payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
    if not _present(payload.top_level_category) or not _present(payload.subcategory):
        return None
    return f"{payload.top_level_category.strip()} / {payload.subcategory.strip()}"
