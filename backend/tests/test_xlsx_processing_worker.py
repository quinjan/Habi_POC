from copy import copy
from io import BytesIO
import json

from openpyxl import Workbook
from openpyxl.styles import PatternFill
from sqlalchemy import select

from backend.app.processing.worker import run_once


def _create_project(client):
    return client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "contractor_assigned": "Internal",
        },
    ).json()


def _upload(client, project_id: int, content: bytes):
    return client.post(
        f"/api/project-workspaces/{project_id}/source-files",
        files={
            "files": (
                "purchase-log.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()


def _workbook_bytes(configure=None) -> bytes:
    workbook = Workbook()
    if configure is not None:
        configure(workbook)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class NoUsableRegionsProvider:
    provider_name = "fake"
    model = "fake-xlsx-model"

    def profile_worksheet(self, *, worksheet: dict, source_submission_id: int):
        return {
            "worksheet_name": worksheet["worksheet"]["name"],
            "title_rows": [],
            "header_rows": [],
            "regions": [],
        }


class ValidXlsxProvider:
    provider_name = "fake"
    model = "fake-xlsx-model"

    def __init__(self, *, source_file_id: int):
        self.source_file_id = source_file_id
        self.profile_calls = []
        self.extraction_calls = []

    def profile_worksheet(self, *, worksheet: dict, source_submission_id: int):
        self.profile_calls.append((worksheet, source_submission_id))
        return {
            "worksheet_name": worksheet["worksheet"]["name"],
            "title_rows": [],
            "header_rows": [1],
            "regions": [
                {
                    "region_id": "purchases",
                    "usable": True,
                    "unusable_reason": None,
                    "header_row_numbers": [1],
                    "body_start_row": 2,
                    "body_end_row": 3,
                    "columns": {
                        "name": "A",
                        "quantity": "B",
                        "unit": "C",
                        "price": "D",
                    },
                }
            ],
        }

    def extract_worksheet_chunk(
        self,
        *,
        profile: dict,
        region: dict,
        rows: list[dict],
        context_rows: list[dict],
        source_submission_id: int,
    ):
        self.extraction_calls.append(
            {
                "profile": profile,
                "region": region,
                "rows": rows,
                "context_rows": context_rows,
                "source_submission_id": source_submission_id,
            }
        )
        return {
            "candidates": [
                {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "quantity": "20",
                    "unit": "pcs",
                    "price": "1500",
                    "currency": "PHP",
                    "currency_state": "source_stated",
                    "provider_name": "ABC Trading",
                    "purchase_date": None,
                    "remarks_or_terms": None,
                    "confidence": 0.94,
                    "category_suggestion": {
                        "top_level_category": "Plumbing",
                        "subcategory": "Pipes",
                    },
                    "evidence": {
                        "source_submission_id": source_submission_id,
                        "source_file_id": self.source_file_id,
                        "worksheet": "Purchases",
                        "region_id": "purchases",
                        "primary_body_row": 2,
                        "locators": [{"row": 2, "role": "body"}],
                    },
                }
            ]
        }


class ChunkRecordingProvider:
    provider_name = "fake"
    model = "fake-xlsx-model"

    def __init__(self):
        self.extraction_calls = []

    def profile_worksheet(self, *, worksheet: dict, source_submission_id: int):
        row_numbers = [cell["row"] for cell in worksheet["cells"]]
        return {
            "worksheet_name": worksheet["worksheet"]["name"],
            "title_rows": [],
            "header_rows": [1],
            "regions": [
                {
                    "region_id": "purchases",
                    "usable": True,
                    "unusable_reason": None,
                    "header_row_numbers": [1],
                    "body_start_row": 2,
                    "body_end_row": max(row_numbers),
                    "columns": {"name": "A"},
                }
            ],
        }

    def extract_worksheet_chunk(self, **kwargs):
        self.extraction_calls.append(kwargs)
        return {"candidates": []}


class InvalidLocatorProvider(ValidXlsxProvider):
    def extract_worksheet_chunk(self, **kwargs):
        result = super().extract_worksheet_chunk(**kwargs)
        result["candidates"][0]["evidence"]["locators"] = [
            {"row": 999, "role": "body"}
        ]
        result["candidates"][0]["evidence"]["primary_body_row"] = 999
        return result


class PartialFailureProvider(ValidXlsxProvider):
    def __init__(self, *, source_file_id: int):
        super().__init__(source_file_id=source_file_id)
        self.attempt_count = 0

    def extract_worksheet_chunk(self, **kwargs):
        self.attempt_count += 1
        if self.attempt_count == 2:
            raise RuntimeError("second extraction call failed")
        return super().extract_worksheet_chunk(**kwargs)


def test_corrupt_xlsx_is_preserved_and_processing_fails_without_review_batch(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)
    submission = _upload(client, project["id"], b"not-an-openxml-workbook")

    assert run_once(client.app.state.session_factory, ai_provider=object()) == 1

    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]
    assert job["status"] == "failed"
    assert job["review_batch_id"] is None
    assert job["candidate_count"] == 0
    assert "workbook" in job["error_message"].lower()
    stored_path = tmp_path / submission["source_file"]["storage_path"]
    assert stored_path.read_bytes() == b"not-an-openxml-workbook"


def test_xlsx_processing_retains_visible_worksheet_artifact_and_skip_diagnostics(
    client, monkeypatch, tmp_path
):
    from backend.app.xlsx.models import WorksheetArtifact

    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)

    def configure(workbook):
        visible = workbook.active
        visible.title = "Purchases"
        visible.append(["Item", "Price", "Hidden Column"])
        visible.append(["PVC pipe", 1500, "ignore me"])
        visible.append(["Hidden row", 999, None])
        visible.row_dimensions[3].hidden = True
        visible.column_dimensions["C"].hidden = True
        hidden = workbook.create_sheet("Internal Notes")
        hidden.sheet_state = "hidden"
        hidden["A1"] = "ignore this sheet"

    submission = _upload(client, project["id"], _workbook_bytes(configure))

    assert run_once(
        client.app.state.session_factory, ai_provider=NoUsableRegionsProvider()
    ) == 1

    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]
    assert job["status"] == "no_candidates_found"
    assert job["diagnostics"]["visible_worksheet_count"] == 1
    assert job["diagnostics"]["hidden_worksheet_count"] == 1
    assert job["diagnostics"]["hidden_row_count"] == 1
    assert job["diagnostics"]["hidden_column_count"] == 1
    assert job["diagnostics"]["artifact_count"] == 1

    with client.app.state.session_factory() as session:
        artifacts = session.scalars(select(WorksheetArtifact)).all()
        assert len(artifacts) == 1
        artifact = artifacts[0]
        assert artifact.worksheet_name == "Purchases"
        artifact_content = json.loads((tmp_path / artifact.artifact_path).read_text())

    assert [cell["coordinate"] for cell in artifact_content["cells"]] == [
        "A1",
        "B1",
        "A2",
        "B2",
    ]


def test_xlsx_processing_rejects_post_open_workbook_limits_without_artifacts(
    client, monkeypatch, tmp_path
):
    from backend.app.xlsx.models import WorksheetArtifact

    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("HABI_XLSX_MAX_NON_EMPTY_ROWS", "1")
    project = _create_project(client)

    def configure(workbook):
        sheet = workbook.active
        sheet.append(["Item"])
        sheet.append(["PVC pipe"])

    submission = _upload(client, project["id"], _workbook_bytes(configure))
    run_once(client.app.state.session_factory, ai_provider=NoUsableRegionsProvider())
    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]

    assert job["status"] == "failed"
    assert "rows limit" in job["error_message"]
    assert job["diagnostics"]["visible_non_empty_row_count"] == 2
    assert job["review_batch_id"] is None
    with client.app.state.session_factory() as session:
        assert session.scalars(select(WorksheetArtifact)).all() == []


def test_worksheet_artifact_retains_formula_merge_format_and_style_metadata(
    client, monkeypatch, tmp_path
):
    from backend.app.xlsx.models import WorksheetArtifact

    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)

    def configure(workbook):
        sheet = workbook.active
        sheet.title = "Purchases"
        sheet.merge_cells("A1:D1")
        sheet["A1"] = "Purchase Log"
        bold_font = copy(sheet["A1"].font)
        bold_font.bold = True
        sheet["A1"].font = bold_font
        sheet["A1"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
        sheet.append(["Item", "Qty", "Unit", "Price", "Total"])
        sheet.append(["PVC pipe", 2, "pcs", 1500, "=B3*D3"])
        sheet["D3"].number_format = "#,##0.00"

    submission = _upload(client, project["id"], _workbook_bytes(configure))
    run_once(client.app.state.session_factory, ai_provider=NoUsableRegionsProvider())

    with client.app.state.session_factory() as session:
        artifact = session.scalar(
            select(WorksheetArtifact).where(
                WorksheetArtifact.source_file_id == submission["source_file"]["id"]
            )
        )
        assert artifact is not None
        content = json.loads((tmp_path / artifact.artifact_path).read_text())

    assert content["worksheet"]["merged_ranges"] == ["A1:D1"]
    by_coordinate = {cell["coordinate"]: cell for cell in content["cells"]}
    assert by_coordinate["A1"]["is_bold"] is True
    assert by_coordinate["A1"]["has_fill"] is True
    assert by_coordinate["D3"]["raw_value"] == 1500
    assert by_coordinate["D3"]["normalized_value"] == 1500
    assert by_coordinate["D3"]["displayed_text"] == "1500"
    assert by_coordinate["D3"]["cell_type"] == "number"
    assert by_coordinate["D3"]["number_format"] == "#,##0.00"
    assert by_coordinate["E3"]["formula"] == "=B3*D3"
    assert by_coordinate["E3"]["raw_value"] is None
    assert by_coordinate["E3"]["cell_type"] == "formula"


def test_xlsx_processing_profiles_then_extracts_verified_candidates(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)

    def configure(workbook):
        sheet = workbook.active
        sheet.title = "Purchases"
        sheet.append(["Item", "Qty", "Unit", "Price"])
        sheet.append(["PVC pipe", 20, "pcs", 1500])
        sheet.append(["Cement", 10, "bags", 2800])

    submission = _upload(client, project["id"], _workbook_bytes(configure))
    provider = ValidXlsxProvider(source_file_id=submission["source_file"]["id"])

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job_detail = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()
    assert job_detail["processing_job"]["status"] == "review_ready"
    assert job_detail["processing_job"]["candidate_count"] == 1
    assert len(provider.profile_calls) == 1
    assert len(provider.extraction_calls) == 1
    extraction_call = provider.extraction_calls[0]
    assert extraction_call["region"]["source_file_id"] == submission["source_file"]["id"]
    assert extraction_call["region"]["worksheet"] == "Purchases"
    assert [row["row"] for row in extraction_call["rows"]] == [2, 3]
    assert [row["row"] for row in extraction_call["context_rows"]] == [1]
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job_detail['review_batch_id']}"
    ).json()
    candidate = review["candidates"][0]
    assert candidate["source_file"]["original_filename"] == "purchase-log.xlsx"
    assert candidate["proposed_payload"]["name"] == "PVC pipe"
    assert candidate["proposed_payload"]["evidence"] == {
        "source_submission_id": submission["source_submission"]["id"],
        "source_file_id": submission["source_file"]["id"],
        "worksheet": "Purchases",
        "region_id": "purchases",
        "primary_body_row": 2,
        "locators": [{"row": 2, "role": "body"}],
    }


def test_xlsx_extraction_chunks_are_independent_and_respect_configured_row_limit(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("HABI_XLSX_EXTRACTION_CHUNK_ROWS", "2")
    project = _create_project(client)

    def configure(workbook):
        sheet = workbook.active
        sheet.title = "Purchases"
        sheet.append(["Item"])
        for index in range(5):
            sheet.append([f"Item {index}"])

    submission = _upload(client, project["id"], _workbook_bytes(configure))
    provider = ChunkRecordingProvider()
    run_once(client.app.state.session_factory, ai_provider=provider)
    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]

    assert job["status"] == "no_candidates_found"
    assert [len(call["rows"]) for call in provider.extraction_calls] == [2, 2, 1]
    assert all(
        [row["row"] for row in call["context_rows"]] == [1]
        for call in provider.extraction_calls
    )
    assert job["diagnostics"]["extraction_chunk_count"] == 3


def test_xlsx_candidate_with_unverified_locator_is_dropped_before_review(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)

    def configure(workbook):
        sheet = workbook.active
        sheet.title = "Purchases"
        sheet.append(["Item", "Qty", "Unit", "Price"])
        sheet.append(["PVC pipe", 20, "pcs", 1500])
        sheet.append(["Cement", 10, "bags", 2800])

    submission = _upload(client, project["id"], _workbook_bytes(configure))
    provider = InvalidLocatorProvider(source_file_id=submission["source_file"]["id"])
    run_once(client.app.state.session_factory, ai_provider=provider)
    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]

    assert job["status"] == "no_candidates_found"
    assert job["review_batch_id"] is None
    assert job["diagnostics"]["raw_candidate_count"] == 1
    assert job["diagnostics"]["valid_candidate_count"] == 0
    assert job["diagnostics"]["dropped_candidate_count"] == 1


def test_xlsx_technical_failure_creates_no_partial_review_output_and_retains_artifacts(
    client, monkeypatch, tmp_path
):
    from backend.app.review.models import ExtractedCandidate, ReviewBatch
    from backend.app.xlsx.models import WorksheetArtifact

    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("HABI_XLSX_EXTRACTION_CHUNK_ROWS", "1")
    project = _create_project(client)

    def configure(workbook):
        sheet = workbook.active
        sheet.title = "Purchases"
        sheet.append(["Item", "Qty", "Unit", "Price"])
        sheet.append(["PVC pipe", 20, "pcs", 1500])
        sheet.append(["Cement", 10, "bags", 2800])

    submission = _upload(client, project["id"], _workbook_bytes(configure))
    provider = PartialFailureProvider(source_file_id=submission["source_file"]["id"])
    run_once(client.app.state.session_factory, ai_provider=provider)
    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]

    assert job["status"] == "failed"
    assert job["review_batch_id"] is None
    assert "second extraction call failed" in job["error_message"]
    with client.app.state.session_factory() as session:
        assert session.scalars(select(ReviewBatch)).all() == []
        assert session.scalars(select(ExtractedCandidate)).all() == []
        artifact = session.scalar(select(WorksheetArtifact))
        assert artifact is not None
        assert artifact.profile is not None
        assert (tmp_path / artifact.artifact_path).exists()


def test_unexpected_xlsx_processor_error_marks_job_failed(
    client, monkeypatch, tmp_path
):
    import backend.app.processing.worker as worker

    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)
    submission = _upload(client, project["id"], b"preserved-source")

    def raise_unexpected(*args, **kwargs):
        raise RuntimeError("unexpected processor failure")

    monkeypatch.setattr(worker, "process_xlsx_source_file", raise_unexpected)

    assert worker.run_once(client.app.state.session_factory, ai_provider=object()) == 1
    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]
    assert job["status"] == "failed"
    assert job["finished_at"] is not None
    assert job["error_message"] == "unexpected processor failure"


def test_approved_xlsx_candidate_imports_verified_spreadsheet_evidence(
    client, monkeypatch, tmp_path
):
    from backend.app.evidence.models import EvidenceRecord

    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)

    def configure(workbook):
        sheet = workbook.active
        sheet.title = "Purchases"
        sheet.append(["Item", "Qty", "Unit", "Price"])
        sheet.append(["PVC pipe", 20, "pcs", 1500])
        sheet.append(["Cement", 10, "bags", 2800])

    submission = _upload(client, project["id"], _workbook_bytes(configure))
    provider = ValidXlsxProvider(source_file_id=submission["source_file"]["id"])
    run_once(client.app.state.session_factory, ai_provider=provider)
    job_detail = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job_detail['review_batch_id']}"
    ).json()
    candidate = review["candidates"][0]

    draft = client.put(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job_detail['review_batch_id']}/review-draft",
        json={
            "candidates": [
                {
                    "candidate_id": candidate["id"],
                    "included": True,
                    "reviewed_payload": {
                        "line_type": "material",
                        "name": "PVC pipe",
                        "top_level_category": "Plumbing",
                        "subcategory": "Pipes",
                        "quantity": "20",
                        "unit": "pcs",
                        "price": "1500",
                        "currency": "PHP",
                        "provider_name": "ABC Trading",
                    },
                }
            ]
        },
    )
    imported = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job_detail['review_batch_id']}/import"
    )

    assert draft.status_code == 200
    assert imported.status_code == 200
    purchase_lines = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines"
    ).json()["items"]
    assert purchase_lines[0]["source_label"] == "purchase-log.xlsx"
    with client.app.state.session_factory() as session:
        evidence = session.scalar(select(EvidenceRecord))
        assert evidence is not None
        assert evidence.manual_source_entry_id is None
        assert evidence.source_file_id == submission["source_file"]["id"]
        assert evidence.source_label == "purchase-log.xlsx"
        assert evidence.content == candidate["proposed_payload"]["evidence"]
