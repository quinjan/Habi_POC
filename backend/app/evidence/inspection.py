import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.evidence.models import EvidenceAnnotation, EvidenceRecord
from backend.app.memory.models import MemoryRecord
from backend.app.projects.schemas import (
    EvidenceAnnotationRead,
    EvidenceAnnotationTargetRead,
    PurchaseLineEvidenceRead,
)
from backend.app.sources.models import ManualSourceEntry, SourceFile, SourceSubmission


def build_purchase_line_evidence_read(
    session: Session,
    *,
    project_workspace_id: int,
    evidence: EvidenceRecord,
) -> PurchaseLineEvidenceRead:
    source_submission_id, source_type = evidence_source_info(session, evidence)
    annotations = evidence_annotation_reads(session, evidence.id)
    locator = strongest_evidence_locator(
        evidence_locator(evidence.content),
        *(annotation.source_locator for annotation in annotations),
    )
    return PurchaseLineEvidenceRead(
        id=evidence.id,
        source_submission_id=source_submission_id,
        source_label=evidence.source_label,
        source_type=source_type,
        source_submission_href=(
            f"/projects/{project_workspace_id}/sources/{source_submission_id}"
        ),
        locator=locator,
        supporting_content=evidence.content,
        annotations=annotations,
        annotation_omitted_count=int(evidence.content.get("annotation_omitted_count", 0)),
        annotation_detected_count=int(evidence.content.get("annotation_detected_count", 0)),
    )


def evidence_annotation_reads(
    session: Session,
    evidence_record_id: int,
) -> list[EvidenceAnnotationRead]:
    annotations = list(
        session.scalars(
            select(EvidenceAnnotation)
            .where(EvidenceAnnotation.evidence_record_id == evidence_record_id)
            .order_by(EvidenceAnnotation.id)
        )
    )
    reads: list[EvidenceAnnotationRead] = []
    for annotation in annotations:
        target = session.get(MemoryRecord, annotation.memory_record_id)
        if target is None:
            continue
        reads.append(
            EvidenceAnnotationRead(
                id=annotation.id,
                proposal_id=annotation.proposal_id,
                text=annotation.text,
                annotation_type=annotation.annotation_type,
                target=EvidenceAnnotationTargetRead(
                    memory_record_id=target.id,
                    record_type=target.record_type,
                    name=target.display_name,
                ),
                source_excerpt=annotation.source_excerpt,
                source_locator=annotation.source_locator,
                provenance=annotation.provenance,
            )
        )
    return reads


def evidence_source_info(session: Session, evidence: EvidenceRecord) -> tuple[int, str]:
    if evidence.manual_source_entry_id is not None:
        manual_entry = session.get(ManualSourceEntry, evidence.manual_source_entry_id)
        if manual_entry is not None:
            return manual_entry.source_submission_id, manual_entry.entry_type
    if evidence.source_file_id is not None:
        source_file = session.get(SourceFile, evidence.source_file_id)
        if source_file is not None:
            return source_file.source_submission_id, "xlsx"
    raise RuntimeError("Evidence Record references a missing source")


def source_submitted_at(session: Session, source_submission_id: int):
    source = session.get(SourceSubmission, source_submission_id)
    if source is None:
        raise RuntimeError("Evidence Record references a missing Source Submission")
    return source.submitted_at


def evidence_locator(content: dict) -> dict | None:
    if isinstance(content.get("locators"), list):
        return {
            "kind": "xlsx_rows",
            "worksheet": content.get("worksheet"),
            "rows": content["locators"],
        }
    if "original_text" in content:
        return {"kind": "manual_text", "field_path": "original_text"}
    return {"kind": "structured_manual"} if content else None


def strongest_evidence_locator(*locators: dict | None) -> dict | None:
    available = [
        locator
        for locator in locators
        if isinstance(locator, dict) and locator and _locator_strength(locator) > 0
    ]
    return max(available, key=_locator_strength, default=None)


def _locator_strength(locator: dict) -> int:
    kind = locator.get("kind")
    if kind == "text_span":
        start = locator.get("start")
        end = locator.get("end")
        if type(start) is int and type(end) is int and start >= 0 and end > start:
            return 40
        return 0
    if kind == "xlsx_cell":
        worksheet = locator.get("worksheet")
        coordinate = locator.get("coordinate")
        if (
            isinstance(worksheet, str)
            and worksheet.strip()
            and isinstance(coordinate, str)
            and re.fullmatch(r"\$?[A-Z]{1,3}\$?[1-9]\d*", coordinate.strip(), re.IGNORECASE)
        ):
            return 40
        return 0
    if (
        kind == "structured_field"
        and isinstance(locator.get("field_path"), str)
        and locator["field_path"].strip()
    ):
        return 40
    if kind in {"pdf_region", "image_region"}:
        return 40
    if kind == "xlsx_rows" and isinstance(locator.get("rows"), list) and locator["rows"]:
        return 20
    if kind in {"manual_text", "structured_manual"}:
        return 10
    return 0
