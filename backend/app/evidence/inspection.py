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
        evidence.content,
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


def strongest_evidence_locator(
    source_content: dict,
    *locators: dict | None,
) -> dict | None:
    available = [
        locator
        for locator in locators
        if isinstance(locator, dict)
        and locator
        and _locator_strength(source_content, locator) > 0
    ]
    return max(
        available,
        key=lambda locator: _locator_strength(source_content, locator),
        default=None,
    )


def _locator_strength(source_content: dict, locator: dict) -> int:
    kind = locator.get("kind")
    if kind in {"text_span", "xlsx_cell", "structured_field"} and (
        source_excerpt_at_locator(source_content, locator) is not None
    ):
        return 40
    if (
        kind == "xlsx_rows"
        and isinstance(locator.get("rows"), list)
        and locator["rows"]
        and locator.get("worksheet") == source_content.get("worksheet")
        and locator["rows"] == source_content.get("locators")
    ):
        return 20
    if (
        kind == "manual_text"
        and locator.get("field_path") == "original_text"
        and isinstance(source_content.get("original_text"), str)
    ):
        return 10
    if (
        kind == "structured_manual"
        and bool(source_content)
        and "original_text" not in source_content
        and not isinstance(source_content.get("locators"), list)
    ):
        return 10
    return 0


_MISSING = object()


def source_excerpt_at_locator(source_content: dict, locator: dict) -> str | None:
    kind = locator.get("kind")
    if kind == "text_span":
        original_text = source_content.get("original_text")
        start = locator.get("start")
        end = locator.get("end")
        if (
            isinstance(original_text, str)
            and type(start) is int
            and type(end) is int
            and 0 <= start < end <= len(original_text)
        ):
            return original_text[start:end]
        return None

    if kind == "xlsx_cell":
        worksheet = locator.get("worksheet")
        coordinate = _normalized_xlsx_coordinate(locator.get("coordinate"))
        if (
            not isinstance(worksheet, str)
            or not worksheet.strip()
            or worksheet != source_content.get("worksheet")
            or coordinate is None
        ):
            return None
        for cell in source_content.get("row_snapshot", []):
            if not isinstance(cell, dict):
                continue
            if _normalized_xlsx_coordinate(cell.get("coordinate")) == coordinate:
                return str(cell.get("value") or "")
        return None

    if kind == "structured_field":
        value = _structured_source_value(source_content, locator.get("field_path"))
        return value if isinstance(value, str) else None

    return None


def _normalized_xlsx_coordinate(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    coordinate = value.strip()
    if not re.fullmatch(
        r"\$?[A-Z]{1,3}\$?[1-9]\d*", coordinate, re.IGNORECASE
    ):
        return None
    return coordinate.replace("$", "").upper()


def _structured_source_value(content: dict, field_path: object) -> object:
    if not isinstance(field_path, str):
        return _MISSING
    segments = field_path.split(".")
    if len(segments) < 2 or segments[0] != "structured_payload":
        return _MISSING

    current: object = content
    for segment in segments[1:]:
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?", segment)
        if match is None or not isinstance(current, dict):
            return _MISSING
        name, index_text = match.groups()
        if name not in current:
            return _MISSING
        current = current[name]
        if index_text is not None:
            index = int(index_text)
            if not isinstance(current, list) or index >= len(current):
                return _MISSING
            current = current[index]
    return current
