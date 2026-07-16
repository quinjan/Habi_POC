def _create_project(client, name):
    return client.post(
        "/api/project-workspaces",
        json={
            "project_name": name,
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "contractor_assigned": "Internal",
        },
    ).json()


def test_source_submission_detail_shows_immutable_source_and_no_import_state(client):
    project = _create_project(client, "Arnaiz Residence Renovation")
    other_project = _create_project(client, "Ortigas Office Fit-out")
    submitted_payload = {
        "line_type": "material",
        "name": "PVC pipe",
        "annotations": [
            {
                "text": "Delivery included",
                "annotation_type": "delivery_terms",
                "target": "purchase_line",
            }
        ],
    }
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={"entry_type": "structured_row", "structured_payload": submitted_payload},
    ).json()
    source_submission_id = submission["source_submission"]["id"]

    detail = client.get(
        f"/api/project-workspaces/{project['id']}/source-submissions/"
        f"{source_submission_id}"
    )
    cross_project = client.get(
        f"/api/project-workspaces/{other_project['id']}/source-submissions/"
        f"{source_submission_id}"
    )

    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == source_submission_id
    assert body["project_workspace_id"] == project["id"]
    assert body["submission_type"] == "manual_source_entry"
    assert body["source"] == {
        "kind": "structured_manual",
        "structured_payload": submission["manual_source_entry"]["structured_payload"],
        "original_text": None,
        "source_file": None,
    }
    assert body["processing_job"]["id"] == submission["processing_job"]["id"]
    assert body["processing_job"]["status"] == "queued"
    assert body["processing_job"]["error_message"] is None
    assert body["processing_job"]["diagnostics"] is None
    assert body["review_batch"] is None
    assert body["imported_evidence"] == []
    assert body["empty_state"] == "No imported evidence"
    assert cross_project.status_code == 404


def test_original_xlsx_download_is_project_scoped_and_preserves_file_metadata(
    client, monkeypatch, tmp_path
):
    from io import BytesIO

    from openpyxl import Workbook

    monkeypatch.setenv("HABI_STORAGE_ROOT", str(tmp_path))
    workbook = Workbook()
    workbook.active.append(["Line kind", "Material name"])
    workbook.active.append(["Material", "PVC pipe"])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    original_bytes = output.getvalue()
    project = _create_project(client, "Arnaiz Residence Renovation")
    other_project = _create_project(client, "Ortigas Office Fit-out")
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/source-files",
        files={
            "files": (
                "Project Purchases.xlsx",
                original_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()
    source_submission_id = submission["source_submission"]["id"]
    source_file_id = submission["source_file"]["id"]
    endpoint = (
        f"/api/project-workspaces/{project['id']}/source-submissions/"
        f"{source_submission_id}/source-files/{source_file_id}/original"
    )

    downloaded = client.get(endpoint)
    available_detail = client.get(
        f"/api/project-workspaces/{project['id']}/source-submissions/{source_submission_id}"
    )
    cross_project = client.get(
        endpoint.replace(
            f"project-workspaces/{project['id']}",
            f"project-workspaces/{other_project['id']}",
        )
    )
    (tmp_path / submission["source_file"]["storage_path"]).unlink()
    missing = client.get(endpoint)
    missing_detail = client.get(
        f"/api/project-workspaces/{project['id']}/source-submissions/{source_submission_id}"
    )

    assert downloaded.status_code == 200
    assert downloaded.content == original_bytes
    assert downloaded.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "filename*=utf-8''Project%20Purchases.xlsx" in downloaded.headers[
        "content-disposition"
    ]
    assert "storage_path" not in downloaded.headers
    assert cross_project.status_code == 404
    assert missing.status_code == 404
    assert available_detail.json()["source"]["source_file"]["available"] is True
    assert missing_detail.status_code == 200
    assert missing_detail.json()["source"]["source_file"]["available"] is False
