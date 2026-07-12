import hashlib
import os
from pathlib import Path
import tempfile

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.processing.models import ProcessingJob
from backend.app.sources.models import SourceFile, SourceSubmission
from backend.app.xlsx.config import XlsxProcessingConfig


class XlsxUploadTooLarge(ValueError):
    pass


def preserve_xlsx_upload(
    *,
    session: Session,
    project_workspace_id: int,
    upload: UploadFile,
    config: XlsxProcessingConfig,
) -> tuple[SourceSubmission, SourceFile, ProcessingJob]:
    config.storage_root.mkdir(parents=True, exist_ok=True)
    temporary_directory = config.storage_root / ".tmp"
    temporary_directory.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    permanent_path: Path | None = None
    try:
        digest = hashlib.sha256()
        byte_size = 0
        with tempfile.NamedTemporaryFile(
            dir=temporary_directory, delete=False, suffix=".xlsx"
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            while chunk := upload.file.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > config.max_upload_bytes:
                    raise XlsxUploadTooLarge(
                        f"XLSX uploads cannot exceed {config.max_upload_bytes} bytes"
                    )
                digest.update(chunk)
                temporary_file.write(chunk)

        source_submission = SourceSubmission(
            project_workspace_id=project_workspace_id,
            submission_type="source_file",
            entered_by=None,
        )
        session.add(source_submission)
        session.flush()

        source_file = SourceFile(
            project_workspace_id=project_workspace_id,
            source_submission_id=source_submission.id,
            original_filename=upload.filename or "source.xlsx",
            byte_size=byte_size,
            declared_mime_type=upload.content_type,
            sha256_checksum=digest.hexdigest(),
            storage_path=f"pending/{source_submission.id}",
        )
        session.add(source_file)
        session.flush()

        relative_path = Path("source-files") / str(source_file.id) / "original.xlsx"
        permanent_path = config.storage_root / relative_path
        permanent_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary_path, permanent_path)
        temporary_path = None
        source_file.storage_path = relative_path.as_posix()

        processing_job = ProcessingJob(
            project_workspace_id=project_workspace_id,
            source_submission_id=source_submission.id,
            status="queued",
            source_type="source_file",
            processor_name="ai_xlsx_purchase_lines_v1",
            candidate_count=0,
            review_batch_id=None,
        )
        session.add(processing_job)
        session.commit()
        session.refresh(source_submission)
        session.refresh(source_file)
        session.refresh(processing_job)
        return source_submission, source_file, processing_job
    except Exception:
        session.rollback()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        if permanent_path is not None:
            permanent_path.unlink(missing_ok=True)
        raise
