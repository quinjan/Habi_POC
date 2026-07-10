from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class XlsxProcessingConfig:
    storage_root: Path
    max_upload_bytes: int = 25 * 1024 * 1024
    max_visible_worksheets: int = 10
    max_non_empty_rows: int = 2_000
    max_non_empty_cells: int = 50_000
    extraction_chunk_rows: int = 100

    @classmethod
    def from_env(cls) -> "XlsxProcessingConfig":
        default_storage_root = "/app/data" if Path("/app").exists() else ".habi-data"
        return cls(
            storage_root=Path(os.getenv("HABI_STORAGE_ROOT", default_storage_root)),
            max_upload_bytes=int(
                os.getenv("HABI_XLSX_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))
            ),
            max_visible_worksheets=int(
                os.getenv("HABI_XLSX_MAX_VISIBLE_WORKSHEETS", "10")
            ),
            max_non_empty_rows=int(os.getenv("HABI_XLSX_MAX_NON_EMPTY_ROWS", "2000")),
            max_non_empty_cells=int(
                os.getenv("HABI_XLSX_MAX_NON_EMPTY_CELLS", "50000")
            ),
            extraction_chunk_rows=int(
                os.getenv("HABI_XLSX_EXTRACTION_CHUNK_ROWS", "100")
            ),
        )
