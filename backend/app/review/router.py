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
from backend.app.review.models import ExtractedCandidate, ReviewBatch
from backend.app.review.schemas import (
    CandidateDecisionRequest,
    ExtractedCandidateRead,
    ImportedPurchaseLine,
    ImportReviewBatchResponse,
    ReviewBatchDetail,
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
    return ReviewBatchDetail(review_batch=review_batch, candidates=candidates)


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

    candidate.decision = payload.decision
    candidate.status = f"{payload.decision}_for_import"
    candidate.reviewed_payload = (
        payload.reviewed_payload.model_dump(mode="json") if payload.reviewed_payload else None
    )

    candidates = _get_batch_candidates(session, review_batch.id)
    if all(batch_candidate.decision is not None for batch_candidate in candidates):
        review_batch.status = (
            "ready_to_import"
            if any(batch_candidate.decision == "approved" for batch_candidate in candidates)
            else "review_closed_no_import"
        )
    else:
        review_batch.status = "review_in_progress"

    session.commit()
    session.refresh(candidate)
    return candidate


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

    imported_purchase_lines: list[ImportedPurchaseLine] = []
    for candidate in approved_candidates:
        if candidate.reviewed_payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved candidates require reviewed payloads",
            )

        manual_source_entry = session.get(ManualSourceEntry, candidate.manual_source_entry_id)
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
        content=manual_source_entry.structured_payload,
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
