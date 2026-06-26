import os

from fastapi.testclient import TestClient


def make_client(tmp_path):
    os.environ["HABI_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'habi_test.db'}"

    from backend.app.main import create_app

    return TestClient(create_app())


def test_import_rejects_batch_with_pending_candidate(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "All candidates must have a review decision before import"


def test_import_rejects_batch_with_no_approved_candidates(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidate']['id']}/decision",
            json={"decision": "rejected", "reviewed_payload": None},
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "At least one approved candidate is required for import"


def test_import_rejects_approved_candidate_without_resolved_category_path(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidate']['id']}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "quantity": "20",
                    "unit": "pcs",
                    "price": "1500",
                    "provider_name": "ABC Trading",
                    "purchase_date": "2025-07-12",
                },
            },
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Approved candidates require a resolved category path"


def test_import_rejects_batch_from_another_project_workspace(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        other_project = client.post(
            "/api/project-workspaces",
            json={
                "project_name": "Ortigas Office Fit-Out",
                "project_type": "Commercial fit-out",
                "location": "Pasig City",
                "completion_year": 2024,
            },
        ).json()

        response = client.post(
            f"/api/project-workspaces/{other_project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert project["id"] != other_project["id"]
    assert response.status_code == 404
    assert response.json()["detail"] == "Review batch not found"


def test_import_rejects_duplicate_batch_import(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        approve_submission(client, project, submission)
        first_import = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

        second_import = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert first_import.status_code == 200
    assert second_import.status_code == 409
    assert second_import.json()["detail"] == "Review batch already imported"


def create_manual_submission(client: TestClient):
    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={
            "line_type": "material",
            "name": "PVC pipe",
            "quantity": "20",
            "unit": "pcs",
            "price": "1500",
            "provider_name": "ABC Trading",
            "purchase_date": "2025-07-12",
            "remarks_or_terms": "Delivery included",
        },
    ).json()
    return project, submission


def approve_submission(client: TestClient, project: dict, submission: dict):
    return client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidate']['id']}/decision",
        json={
            "decision": "approved",
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
                "purchase_date": "2025-07-12",
                "remarks_or_terms": "Delivery included",
            },
        },
    )
