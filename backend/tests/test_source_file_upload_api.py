import hashlib


def _create_project(client):
    return client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()


def test_source_file_upload_rejects_non_xlsx_without_creating_a_job(client):
    project = _create_project(client)

    response = client.post(
        f"/api/project-workspaces/{project['id']}/source-files",
        files={"files": ("purchase-log.csv", b"item,price", "text/csv")},
    )

    assert response.status_code == 422
    jobs = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs"
    ).json()["items"]
    assert jobs == []


def test_source_file_upload_requires_exactly_one_file(client):
    project = _create_project(client)

    missing = client.post(
        f"/api/project-workspaces/{project['id']}/source-files",
        files={},
    )
    multiple = client.post(
        f"/api/project-workspaces/{project['id']}/source-files",
        files=[
            ("files", ("first.xlsx", b"first", "application/x-test")),
            ("files", ("second.xlsx", b"second", "application/x-test")),
        ],
    )

    assert missing.status_code == 422
    assert multiple.status_code == 422
    assert client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs"
    ).json()["items"] == []


def test_source_file_upload_preserves_bytes_and_queues_processing(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)
    workbook_bytes = b"accepted-at-upload-boundary"

    response = client.post(
        f"/api/project-workspaces/{project['id']}/source-files",
        files={
            "files": (
                "Purchase Log.XLSX",
                workbook_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_submission"]["submission_type"] == "source_file"
    assert body["source_file"]["original_filename"] == "Purchase Log.XLSX"
    assert body["source_file"]["byte_size"] == len(workbook_bytes)
    assert body["source_file"]["declared_mime_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert body["source_file"]["sha256_checksum"] == hashlib.sha256(
        workbook_bytes
    ).hexdigest()
    assert body["source_file"]["uploaded_at"] is not None
    stored_path = tmp_path / body["source_file"]["storage_path"]
    assert stored_path.read_bytes() == workbook_bytes
    assert body["processing_job"]["status"] == "queued"
    assert body["processing_job"]["source_type"] == "source_file"
    assert body["processing_job"]["processor_name"] == "ai_xlsx_purchase_lines_v1"


def test_source_file_upload_rejects_configured_oversize_before_creating_records(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("HABI_XLSX_MAX_UPLOAD_BYTES", "4")
    project = _create_project(client)

    response = client.post(
        f"/api/project-workspaces/{project['id']}/source-files",
        files={"files": ("purchase-log.xlsx", b"12345", "application/x-test")},
    )

    assert response.status_code == 413
    assert client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs"
    ).json()["items"] == []
    permanent_storage = tmp_path / "source-files"
    if permanent_storage.exists():
        assert list(permanent_storage.rglob("*")) == []


def test_identical_xlsx_uploads_create_distinct_immutable_submissions(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)
    files = {"files": ("purchase-log.xlsx", b"same-workbook", "application/x-test")}

    first = client.post(
        f"/api/project-workspaces/{project['id']}/source-files", files=files
    ).json()
    second = client.post(
        f"/api/project-workspaces/{project['id']}/source-files", files=files
    ).json()

    assert first["source_submission"]["id"] != second["source_submission"]["id"]
    assert first["source_file"]["id"] != second["source_file"]["id"]
    assert first["source_file"]["storage_path"] != second["source_file"]["storage_path"]
    assert first["source_file"]["sha256_checksum"] == second["source_file"]["sha256_checksum"]
    assert first["processing_job"]["id"] != second["processing_job"]["id"]


def test_processing_job_queue_includes_source_file_summary(client, monkeypatch, tmp_path):
    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    project = _create_project(client)
    uploaded = client.post(
        f"/api/project-workspaces/{project['id']}/source-files",
        files={"files": ("purchase-log.xlsx", b"workbook", "application/x-test")},
    ).json()

    queue = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs"
    ).json()["items"]

    assert queue[0]["source_file"] == {
        "id": uploaded["source_file"]["id"],
        "original_filename": "purchase-log.xlsx",
        "byte_size": len(b"workbook"),
        "declared_mime_type": "application/x-test",
        "uploaded_at": uploaded["source_file"]["uploaded_at"],
        "sha256_checksum": uploaded["source_file"]["sha256_checksum"],
    }
