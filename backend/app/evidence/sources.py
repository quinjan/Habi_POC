from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.review.models import ExtractedCandidate
from backend.app.sources.models import ManualSourceEntry, SourceFile
from backend.app.xlsx.ai import XlsxCandidateEvidence


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
        content = (
            manual_source_entry.structured_payload
            if manual_source_entry.structured_payload is not None
            else {"original_text": manual_source_entry.original_text}
        )
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
    return CandidateSourceEvidence(
        manual_source_entry_id=None,
        source_file_id=source_file.id,
        source_label=source_file.original_filename,
        content=evidence.model_dump(mode="json"),
    )
