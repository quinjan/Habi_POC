from dataclasses import dataclass
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.review.models import ExtractedCandidate
from backend.app.sources.models import ManualSourceEntry, SourceFile
from backend.app.xlsx.ai import XlsxCandidateEvidence
from backend.app.xlsx.config import XlsxProcessingConfig
from backend.app.xlsx.models import WorksheetArtifact


@dataclass(frozen=True)
class CandidateSourceEvidence:
    manual_source_entry_id: int | None
    source_file_id: int | None
    source_label: str
    content: dict


def candidate_source_evidence(
    *, session: Session, candidate: ExtractedCandidate
) -> CandidateSourceEvidence | None:
    manual_source_entry = session.scalar(
        select(ManualSourceEntry).where(
            ManualSourceEntry.source_submission_id == candidate.source_submission_id,
            ManualSourceEntry.project_workspace_id == candidate.project_workspace_id,
        )
    )
    if manual_source_entry is not None:
        content = dict(
            manual_source_entry.structured_payload
            if manual_source_entry.structured_payload is not None
            else {"original_text": manual_source_entry.original_text}
        )
        _copy_annotation_limit_metadata(candidate.proposed_payload, content)
        return CandidateSourceEvidence(
            manual_source_entry_id=manual_source_entry.id,
            source_file_id=None,
            source_label="Manual Source Entry",
            content=content,
        )

    source_file = session.scalar(
        select(SourceFile).where(
            SourceFile.source_submission_id == candidate.source_submission_id,
            SourceFile.project_workspace_id == candidate.project_workspace_id,
        )
    )
    if source_file is None:
        return None
    try:
        evidence = XlsxCandidateEvidence.model_validate(
            candidate.proposed_payload.get("evidence")
        )
    except (TypeError, ValueError):
        return None
    if (
        evidence.source_submission_id != candidate.source_submission_id
        or evidence.source_file_id != source_file.id
    ):
        return None
    content = evidence.model_dump(mode="json")
    _add_xlsx_row_snapshot(
        session=session,
        candidate=candidate,
        evidence=evidence,
        content=content,
    )
    _copy_annotation_limit_metadata(candidate.proposed_payload, content)
    return CandidateSourceEvidence(
        manual_source_entry_id=None,
        source_file_id=source_file.id,
        source_label=source_file.original_filename,
        content=content,
    )


def _copy_annotation_limit_metadata(candidate_payload: dict, evidence_content: dict) -> None:
    for field in ("annotation_omitted_count", "annotation_detected_count"):
        value = candidate_payload.get(field)
        if isinstance(value, int) and value > 0:
            evidence_content[field] = value


def _add_xlsx_row_snapshot(
    *,
    session: Session,
    candidate: ExtractedCandidate,
    evidence: XlsxCandidateEvidence,
    content: dict,
) -> None:
    artifact = session.scalar(
        select(WorksheetArtifact).where(
            WorksheetArtifact.source_file_id == evidence.source_file_id,
            WorksheetArtifact.project_workspace_id == candidate.project_workspace_id,
            WorksheetArtifact.worksheet_name == evidence.worksheet,
        )
    )
    if artifact is None:
        return
    artifact_path = XlsxProcessingConfig.from_env().storage_root / Path(
        artifact.artifact_path
    )
    try:
        artifact_content = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    cells = artifact_content.get("cells", [])
    body_cells = {
        cell["column"]: cell
        for cell in cells
        if cell.get("row") == evidence.primary_body_row
    }
    header_rows = sorted(
        {
            *artifact_content.get("profile", {}).get("header_rows", []),
            *(
                artifact.profile.get("header_rows", [])
                if isinstance(artifact.profile, dict)
                else []
            ),
        }
    )
    header_cells = {
        cell["column"]: cell
        for cell in cells
        if cell.get("row") in header_rows
    }
    annotation_coordinates = {
        proposal.get("source_locator", {}).get("coordinate")
        for proposal in candidate.proposed_payload.get("annotation_proposals", [])
        if isinstance(proposal, dict)
    }
    content["row_snapshot"] = [
        {
            "column": column,
            "coordinate": body_cell.get("coordinate"),
            "header": header_cells.get(column, {}).get("displayed_text"),
            "value": body_cell.get("displayed_text"),
            "annotation": body_cell.get("coordinate") in annotation_coordinates,
        }
        for column, body_cell in sorted(body_cells.items())
    ]
