from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.evidence.inspection import evidence_annotation_reads, evidence_locator
from backend.app.evidence.models import EvidenceRecord, MemoryRecordEvidenceLink
from backend.app.memory.models import MemoryRecord, PurchaseLine, PurchaseLineConceptLink
from backend.app.processing.models import ProcessingJob
from backend.app.projects.models import ProjectWorkspace
from backend.app.review.models import ReviewBatch
from backend.app.review.schemas import ManualSourceEntryQueuedSubmission, SourceFileQueuedSubmission
from backend.app.sources.models import ManualSourceEntry, SourceFile, SourceSubmission
from backend.app.sources.schemas import (
    ManualSourceEntryCreate,
    SourceFileInspectionRead,
    SourceReviewBatchLinkRead,
    SourceSubmissionContentRead,
    SourceSubmissionDetail,
    SourceImportedEvidenceRead,
    SourceLinkedRecordRead,
    SourcePurchaseLineLinkRead,
)
from backend.app.taxonomy.models import TaxonomyNode
from backend.app.xlsx.config import XlsxProcessingConfig
from backend.app.xlsx.upload import XlsxUploadTooLarge, preserve_xlsx_upload


router = APIRouter(tags=["manual-source-entries"])


@router.get(
    "/{project_workspace_id}/source-submissions/{source_submission_id}",
    response_model=SourceSubmissionDetail,
)
def get_source_submission_detail(
    project_workspace_id: int,
    source_submission_id: int,
    session: Session = Depends(get_session),
) -> SourceSubmissionDetail:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project workspace not found",
        )
    source_submission = session.scalar(
        select(SourceSubmission).where(
            SourceSubmission.id == source_submission_id,
            SourceSubmission.project_workspace_id == project_workspace_id,
        )
    )
    if source_submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source Submission not found",
        )
    manual_entry = session.scalar(
        select(ManualSourceEntry).where(
            ManualSourceEntry.source_submission_id == source_submission.id,
            ManualSourceEntry.project_workspace_id == project_workspace_id,
        )
    )
    source_file = session.scalar(
        select(SourceFile).where(
            SourceFile.source_submission_id == source_submission.id,
            SourceFile.project_workspace_id == project_workspace_id,
        )
    )
    processing_job = session.scalar(
        select(ProcessingJob).where(
            ProcessingJob.source_submission_id == source_submission.id,
            ProcessingJob.project_workspace_id == project_workspace_id,
        )
    )
    review_batch = session.scalar(
        select(ReviewBatch).where(
            ReviewBatch.source_submission_id == source_submission.id,
            ReviewBatch.project_workspace_id == project_workspace_id,
        )
    )
    if manual_entry is not None:
        source = SourceSubmissionContentRead(
            kind=(
                "structured_manual"
                if manual_entry.entry_type == "structured_row"
                else "free_form_text"
            ),
            structured_payload=manual_entry.structured_payload,
            original_text=manual_entry.original_text,
            source_file=None,
        )
    elif source_file is not None:
        source_file_path = (
            XlsxProcessingConfig.from_env().storage_root / Path(source_file.storage_path)
        )
        source = SourceSubmissionContentRead(
            kind="xlsx",
            source_file=SourceFileInspectionRead(
                id=source_file.id,
                original_filename=source_file.original_filename,
                byte_size=source_file.byte_size,
                declared_mime_type=source_file.declared_mime_type,
                uploaded_at=source_file.uploaded_at,
                sha256_checksum=source_file.sha256_checksum,
                available=source_file_path.is_file(),
            ),
        )
    else:
        raise RuntimeError("Source Submission has no source content")
    evidence_query = select(EvidenceRecord).where(
        EvidenceRecord.project_workspace_id == project_workspace_id
    )
    if manual_entry is not None:
        evidence_query = evidence_query.where(
            EvidenceRecord.manual_source_entry_id == manual_entry.id
        )
    elif source_file is not None:
        evidence_query = evidence_query.where(EvidenceRecord.source_file_id == source_file.id)
    imported_evidence = [
        _source_imported_evidence_read(
            session,
            project_workspace_id=project_workspace_id,
            evidence=evidence,
        )
        for evidence in session.scalars(evidence_query.order_by(EvidenceRecord.id))
    ]
    return SourceSubmissionDetail(
        id=source_submission.id,
        project_workspace_id=source_submission.project_workspace_id,
        submission_type=source_submission.submission_type,
        submitted_at=source_submission.submitted_at,
        source=source,
        processing_job=processing_job,
        review_batch=(
            SourceReviewBatchLinkRead(
                id=review_batch.id,
                status=review_batch.status,
                href=f"/projects/{project_workspace_id}/review-batches/{review_batch.id}",
            )
            if review_batch is not None
            else None
        ),
        imported_evidence=imported_evidence,
        empty_state=None if imported_evidence else "No imported evidence",
    )


@router.get(
    "/{project_workspace_id}/source-submissions/{source_submission_id}/"
    "source-files/{source_file_id}/original",
    response_class=FileResponse,
)
def get_original_source_file(
    project_workspace_id: int,
    source_submission_id: int,
    source_file_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    source_submission = session.scalar(
        select(SourceSubmission).where(
            SourceSubmission.id == source_submission_id,
            SourceSubmission.project_workspace_id == project_workspace_id,
        )
    )
    source_file = session.scalar(
        select(SourceFile).where(
            SourceFile.id == source_file_id,
            SourceFile.project_workspace_id == project_workspace_id,
            SourceFile.source_submission_id == source_submission_id,
        )
    )
    if source_submission is None or source_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original Source File not found",
        )
    path = XlsxProcessingConfig.from_env().storage_root / Path(source_file.storage_path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original file unavailable",
        )
    return FileResponse(
        path=path,
        media_type=(
            source_file.declared_mime_type
            or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        filename=source_file.original_filename,
    )


def _source_imported_evidence_read(
    session: Session,
    *,
    project_workspace_id: int,
    evidence: EvidenceRecord,
) -> SourceImportedEvidenceRead:
    linked_record_ids = set(
        session.scalars(
            select(MemoryRecordEvidenceLink.memory_record_id).where(
                MemoryRecordEvidenceLink.evidence_record_id == evidence.id
            )
        )
    )
    purchase_lines = list(
        session.scalars(
            select(PurchaseLine)
            .where(
                PurchaseLine.project_workspace_id == project_workspace_id,
                PurchaseLine.memory_record_id.in_(linked_record_ids),
            )
            .order_by(PurchaseLine.id)
        )
    )
    purchase_line_links: list[SourcePurchaseLineLinkRead] = []
    for purchase_line in purchase_lines:
        purchase_record = session.get(MemoryRecord, purchase_line.memory_record_id)
        concept_record_ids = list(
            session.scalars(
                select(PurchaseLineConceptLink.concept_memory_record_id)
                .where(PurchaseLineConceptLink.purchase_line_id == purchase_line.id)
                .order_by(PurchaseLineConceptLink.id)
            )
        )
        record_ids = concept_record_ids
        if purchase_line.provider_memory_record_id is not None:
            record_ids.append(purchase_line.provider_memory_record_id)
        linked_records: list[SourceLinkedRecordRead] = []
        for record_id in record_ids:
            record = session.get(MemoryRecord, record_id)
            if record is None:
                continue
            linked_records.append(
                SourceLinkedRecordRead(
                    memory_record_id=record.id,
                    record_type=record.record_type,
                    name=record.display_name,
                    category_path=_source_taxonomy_path(session, record.taxonomy_node_id),
                )
            )
        purchase_line_links.append(
            SourcePurchaseLineLinkRead(
                id=purchase_line.id,
                status=purchase_record.status if purchase_record is not None else "unknown",
                href=(
                    f"/projects/{project_workspace_id}/purchase-lines/{purchase_line.id}"
                ),
                linked_records=linked_records,
            )
        )
    return SourceImportedEvidenceRead(
        id=evidence.id,
        source_label=evidence.source_label,
        locator=evidence_locator(evidence.content),
        supporting_content=evidence.content,
        annotations=evidence_annotation_reads(session, evidence.id),
        purchase_lines=purchase_line_links,
        annotation_omitted_count=int(evidence.content.get("annotation_omitted_count", 0)),
        annotation_detected_count=int(evidence.content.get("annotation_detected_count", 0)),
    )


def _source_taxonomy_path(session: Session, taxonomy_node_id: int) -> str:
    node = session.get(TaxonomyNode, taxonomy_node_id)
    if node is None:
        raise RuntimeError("Memory Record references missing taxonomy")
    if node.parent_id is None:
        return node.name
    parent = session.get(TaxonomyNode, node.parent_id)
    return f"{parent.name} / {node.name}" if parent is not None else node.name


@router.post(
    "/{project_workspace_id}/source-files",
    response_model=SourceFileQueuedSubmission,
    status_code=status.HTTP_201_CREATED,
)
def create_source_file(
    project_workspace_id: int,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
) -> SourceFileQueuedSubmission:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")
    if len(files) != 1:
        raise HTTPException(status_code=422, detail="Upload exactly one .xlsx file")
    if not (files[0].filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Only .xlsx source files are supported")
    try:
        source_submission, source_file, processing_job = preserve_xlsx_upload(
            session=session,
            project_workspace_id=project_workspace.id,
            upload=files[0],
            config=XlsxProcessingConfig.from_env(),
        )
    except XlsxUploadTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    return SourceFileQueuedSubmission(
        source_submission=source_submission,
        source_file=source_file,
        processing_job=processing_job,
    )


@router.post(
    "/{project_workspace_id}/manual-source-entries",
    response_model=ManualSourceEntryQueuedSubmission,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_source_entry(
    project_workspace_id: int,
    payload: ManualSourceEntryCreate,
    session: Session = Depends(get_session),
) -> ManualSourceEntryQueuedSubmission:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")

    if payload.entry_type == "structured_row" and payload.structured_payload is None:
        raise HTTPException(
            status_code=422,
            detail="Structured manual source entries require structured_payload",
        )
    if payload.entry_type == "free_form_text" and payload.original_text is None:
        raise HTTPException(
            status_code=422,
            detail="Free-form manual source entries require original_text",
        )

    source_submission = SourceSubmission(
        project_workspace_id=project_workspace.id,
        submission_type="manual_source_entry",
        entered_by=None,
    )
    session.add(source_submission)
    session.flush()

    manual_source_entry = ManualSourceEntry(
        project_workspace_id=project_workspace.id,
        source_submission_id=source_submission.id,
        entry_type=payload.entry_type,
        structured_payload=payload.structured_payload.model_dump(mode="json")
        if payload.structured_payload
        else None,
        original_text=payload.original_text if payload.entry_type == "free_form_text" else None,
    )
    session.add(manual_source_entry)
    session.flush()

    processing_job = ProcessingJob(
        project_workspace_id=project_workspace.id,
        source_submission_id=source_submission.id,
        status="queued",
        source_type="manual_source_entry",
        processor_name=_processor_name(payload.entry_type),
        candidate_count=0,
        review_batch_id=None,
    )
    session.add(processing_job)
    session.commit()

    session.refresh(source_submission)
    session.refresh(manual_source_entry)
    session.refresh(processing_job)
    return ManualSourceEntryQueuedSubmission(
        source_submission=source_submission,
        manual_source_entry=manual_source_entry,
        processing_job=processing_job,
    )


def _processor_name(entry_type: str) -> str:
    if entry_type == "structured_row":
        return "structured_manual_row_v1"
    return "ai_manual_free_form_v1"
