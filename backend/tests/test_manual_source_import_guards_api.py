from fastapi.testclient import TestClient

from backend.tests.db import make_postgres_test_client
from backend.tests.manual_submission_helpers import create_review_ready_manual_submission


def make_client(_tmp_path):
    return make_postgres_test_client()


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
                f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
            json={"decision": "rejected", "reviewed_payload": None},
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "At least one approved candidate is required for import"


def test_rejected_batch_stays_in_progress_until_explicit_close_with_no_import(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
            json={"decision": "rejected", "reviewed_payload": None},
        )
        before_close = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

        close_response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/close-with-no-import"
        )
        after_close = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert decision.status_code == 200
    assert before_close.json()["review_batch"]["status"] == "review_in_progress"
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "review_closed_no_import"
    assert after_close.json()["review_batch"]["status"] == "review_closed_no_import"


def test_close_with_no_import_rejects_unresolved_candidates(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/close-with-no-import"
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only fully excluded batches can be closed with no import"


def test_close_with_no_import_rejects_approved_candidates(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        approve_submission(client, project, submission)

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/close-with-no-import"
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only fully excluded batches can be closed with no import"


def test_import_rejects_approved_candidate_without_resolved_category_path(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
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


def test_imported_batch_rejects_later_review_actions(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        approve_submission(client, project, submission)
        imported = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

        decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
            json={"decision": "rejected", "reviewed_payload": None},
        )
        close_response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/close-with-no-import"
        )

    assert imported.status_code == 200
    assert decision.status_code == 409
    assert decision.json()["detail"] == "Terminal review batches cannot be changed"
    assert close_response.status_code == 409
    assert close_response.json()["detail"] == "Terminal review batches cannot be changed"


def test_review_closed_no_import_batch_rejects_later_review_actions(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
            json={"decision": "rejected", "reviewed_payload": None},
        )
        closed = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/close-with-no-import"
        )

        decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
            },
        )
        import_response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )
        close_response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/close-with-no-import"
        )

    assert closed.status_code == 200
    assert decision.status_code == 409
    assert decision.json()["detail"] == "Terminal review batches cannot be changed"
    assert import_response.status_code == 409
    assert import_response.json()["detail"] == "Terminal review batches cannot be imported"
    assert close_response.status_code == 409
    assert close_response.json()["detail"] == "Terminal review batches cannot be changed"


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
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={
            "line_type": "material",
            "name": "PVC pipe",
            "quantity": "20",
            "unit": "pcs",
            "price": "1500",
            "provider_name": "ABC Trading",
            "purchase_date": "2025-07-12",
            "remarks_or_terms": "Delivery included",
        },
    )
    return project, submission


def approve_submission(client: TestClient, project: dict, submission: dict):
    return client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
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
