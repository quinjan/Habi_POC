from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.evidence.models import (
    EvidenceAnnotation,
    EvidenceRecord,
    MemoryRecordEvidenceLink,
)
from backend.app.memory.models import (
    Material,
    MemoryRecord,
    Provider,
    PurchaseLine,
    Service,
)
from backend.app.projects.models import ProjectWorkspace
from backend.app.review.lifecycle import (
    TerminalReviewBatchError,
    apply_candidate_decision,
    close_review_batch_with_no_import,
    detect_duplicate_conflicts,
)
from backend.app.review.models import (
    DuplicateCandidateGroup,
    DuplicateCandidateGroupMember,
    ExtractedCandidate,
    ReviewBatch,
)
from backend.app.review.schemas import (
    CandidateDecisionRequest,
    DuplicateCandidateGroupCreate,
    DuplicateCandidateGroupMembersRequest,
    DuplicateCandidateGroupRead,
    ExtractedCandidateRead,
    ImportedPurchaseLine,
    ImportReviewBatchResponse,
    ReviewBatchDetail,
    ReviewBatchRead,
    ReviewedPurchaseLinePayload,
)
from backend.app.sources.models import ManualSourceEntry
from backend.app.taxonomy.models import TaxonomyNode


router = APIRouter(tags=["review-batches"])


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
    candidates = _get_batch_candidates(session, review_batch.id)
    duplicate_groups = _get_duplicate_group_reads(session, review_batch.id)
    return ReviewBatchDetail(
        review_batch=review_batch,
        candidates=candidates,
        duplicate_groups=duplicate_groups,
        duplicate_conflicts=detect_duplicate_conflicts(
            session=session,
            review_batch=review_batch,
        ),
    )


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
) -> ExtractedCandidate:
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

    try:
        apply_candidate_decision(
            session=session,
            review_batch=review_batch,
            candidate=candidate,
            decision=payload.decision,
            reviewed_payload=payload.reviewed_payload.model_dump(mode="json")
            if payload.reviewed_payload
            else None,
            merged_into_candidate_id=payload.merged_into_candidate_id,
        )
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
    return candidate


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

        manual_source_entry = _manual_entry_for_source_submission(
            session=session,
            source_submission_id=candidate.source_submission_id,
        )
        if manual_source_entry is None or manual_source_entry.project_workspace_id != project_workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved candidates require source evidence",
            )

        payload = ReviewedPurchaseLinePayload.model_validate(candidate.reviewed_payload)
        _validate_importable_payload(payload)
        purchase_line = _import_purchase_line(
            session=session,
            project_workspace_id=project_workspace_id,
            manual_source_entry=manual_source_entry,
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
    session.commit()
    return ImportReviewBatchResponse(imported_purchase_lines=imported_purchase_lines)


def _get_project_review_batch(
    session: Session,
    project_workspace_id: int,
    review_batch_id: int,
) -> ReviewBatch:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")

    review_batch = session.scalar(
        select(ReviewBatch).where(
            ReviewBatch.id == review_batch_id,
            ReviewBatch.project_workspace_id == project_workspace_id,
        )
    )
    if review_batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review batch not found")
    return review_batch


def _get_batch_candidates(session: Session, review_batch_id: int) -> list[ExtractedCandidate]:
    return list(
        session.scalars(
            select(ExtractedCandidate)
            .where(ExtractedCandidate.review_batch_id == review_batch_id)
            .order_by(ExtractedCandidate.id)
        )
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
    if payload.line_type not in {"material", "service"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved candidates require a Material or Service line type",
        )
    if not _present(payload.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved candidates require an item or service name",
        )
    if not _present(payload.top_level_category) or not _present(payload.subcategory):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved candidates require a resolved category path",
        )


def _import_purchase_line(
    *,
    session: Session,
    project_workspace_id: int,
    manual_source_entry: ManualSourceEntry,
    payload: ReviewedPurchaseLinePayload,
) -> PurchaseLine:
    top_level = _get_or_create_taxonomy_node(
        session=session,
        project_workspace_id=project_workspace_id,
        name=payload.top_level_category or "",
        parent_id=None,
    )
    subcategory = _get_or_create_taxonomy_node(
        session=session,
        project_workspace_id=project_workspace_id,
        name=payload.subcategory or "",
        parent_id=top_level.id,
    )
    category_path = f"{top_level.name} / {subcategory.name}"

    item_record = _get_or_create_entity_record(
        session=session,
        project_workspace_id=project_workspace_id,
        record_type=payload.line_type or "material",
        display_name=payload.name or "",
        taxonomy_node_id=subcategory.id,
    )
    if payload.line_type == "material":
        _ensure_type_record(session, Material, item_record.id)
    else:
        _ensure_type_record(session, Service, item_record.id)

    provider_record = None
    provider_name = _clean(payload.provider_name)
    if provider_name is not None:
        provider_record = _get_or_create_entity_record(
            session=session,
            project_workspace_id=project_workspace_id,
            record_type="provider",
            display_name=provider_name,
            taxonomy_node_id=subcategory.id,
        )
        _ensure_type_record(session, Provider, provider_record.id)

    purchase_record = MemoryRecord(
        project_workspace_id=project_workspace_id,
        record_type="purchase_line",
        display_name=payload.name or "",
        normalized_name=_normalize(payload.name or ""),
        taxonomy_node_id=subcategory.id,
        status="active",
    )
    session.add(purchase_record)
    session.flush()

    evidence = EvidenceRecord(
        project_workspace_id=project_workspace_id,
        manual_source_entry_id=manual_source_entry.id,
        source_label="Manual Source Entry",
        content=_manual_source_evidence_content(manual_source_entry),
    )
    session.add(evidence)
    session.flush()

    for record_id in [purchase_record.id, item_record.id, provider_record.id if provider_record else None]:
        if record_id is not None:
            session.add(
                MemoryRecordEvidenceLink(
                    memory_record_id=record_id,
                    evidence_record_id=evidence.id,
                )
            )

    remarks_or_terms = _clean(payload.remarks_or_terms)
    if remarks_or_terms is not None:
        session.add(
            EvidenceAnnotation(
                evidence_record_id=evidence.id,
                memory_record_id=purchase_record.id,
                annotation_type="general qualifier",
                text=remarks_or_terms,
            )
        )

    price = _clean(payload.price)
    currency = _clean(payload.currency) if price is not None else None
    purchase_line = PurchaseLine(
        project_workspace_id=project_workspace_id,
        memory_record_id=purchase_record.id,
        item_memory_record_id=item_record.id,
        provider_memory_record_id=provider_record.id if provider_record else None,
        item_or_service_name=payload.name or "",
        line_type=payload.line_type or "material",
        provider_name=provider_name,
        provider_type="external" if provider_name is not None else "unknown",
        provider_role=_provider_role(payload.line_type, provider_name),
        quantity=_clean(payload.quantity),
        unit=_clean(payload.unit),
        unit_state="known" if _present(payload.unit) else "unknown",
        price=price,
        currency=currency or ("PHP" if price is not None else None),
        price_state="known" if price is not None else "unknown",
        purchase_date=payload.purchase_date,
        date_state="known" if payload.purchase_date is not None else "unknown",
        category_path=category_path,
    )
    session.add(purchase_line)
    session.flush()
    return purchase_line


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
        manual_source_entry = _manual_entry_for_source_submission(
            session=session,
            source_submission_id=merged_candidate.source_submission_id,
        )
        if manual_source_entry is None or manual_source_entry.project_workspace_id != project_workspace_id:
            continue

        evidence = EvidenceRecord(
            project_workspace_id=project_workspace_id,
            manual_source_entry_id=manual_source_entry.id,
            source_label="Manual Source Entry",
            content=_manual_source_evidence_content(manual_source_entry),
        )
        session.add(evidence)
        session.flush()

        record_ids = [
            purchase_line.memory_record_id,
            purchase_line.item_memory_record_id,
            purchase_line.provider_memory_record_id,
        ]
        for record_id in record_ids:
            if record_id is not None:
                session.add(
                    MemoryRecordEvidenceLink(
                        memory_record_id=record_id,
                        evidence_record_id=evidence.id,
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
    taxonomy_node = session.scalar(
        select(TaxonomyNode).where(
            TaxonomyNode.project_workspace_id == project_workspace_id,
            TaxonomyNode.parent_id == parent_id,
            TaxonomyNode.name == cleaned_name,
        )
    )
    if taxonomy_node is not None:
        return taxonomy_node

    taxonomy_node = TaxonomyNode(
        project_workspace_id=project_workspace_id,
        parent_id=parent_id,
        name=cleaned_name,
    )
    session.add(taxonomy_node)
    session.flush()
    return taxonomy_node


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


def _provider_role(line_type: str | None, provider_name: str | None) -> str | None:
    if provider_name is None:
        return None
    return "material_supplier" if line_type == "material" else "service_provider"


def _present(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


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


def _manual_source_evidence_content(manual_source_entry: ManualSourceEntry) -> dict:
    if manual_source_entry.structured_payload is not None:
        return manual_source_entry.structured_payload
    return {"original_text": manual_source_entry.original_text}
