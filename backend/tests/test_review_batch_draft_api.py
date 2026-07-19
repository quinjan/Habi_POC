from fastapi.testclient import TestClient

from backend.tests.db import make_postgres_test_client
from backend.tests.manual_submission_helpers import create_review_ready_manual_submission


def make_client(_tmp_path):
    return make_postgres_test_client()


def test_review_batch_draft_saves_included_and_excluded_candidates(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "service",
                "name": "Hauling",
                "quantity": "1",
                "unit": "lot",
                "price": "8000",
                "provider_name": "JRS Hauling",
                "category_suggestion": {
                    "top_level_category": "Services",
                    "subcategory": "Hauling",
                },
            },
        )

        response = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": submission["candidates"][0]["id"],
                        "included": True,
                        "reviewed_payload": {
                            "line_type": "material",
                            "name": "PVC pipe",
                            "top_level_category": "Plumbing",
                            "subcategory": "Pipes",
                            "quantity": "20",
                            "unit": "pcs",
                            "price": "1500",
                            "provider_name": "ABC Trading",
                        },
                    },
                    {
                        "candidate_id": second_candidate_id,
                        "included": False,
                        "reviewed_payload": None,
                    },
                ]
            },
        )
        gate_id = response.json()["candidates"][0]["taxonomy_gates"][0]["id"]
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{submission['review_batch']['id']}/taxonomy-gates/{gate_id}/accept"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["review_batch"]["status"] == "review_in_progress"
    candidates = {candidate["id"]: candidate for candidate in body["candidates"]}
    assert candidates[submission["candidates"][0]["id"]]["decision"] == "approved"
    assert candidates[submission["candidates"][0]["id"]]["status"] == "approved_for_import"
    assert candidates[submission["candidates"][0]["id"]]["reviewed_payload"]["subcategory"] == "Pipes"
    assert candidates[second_candidate_id]["decision"] == "rejected"
    assert candidates[second_candidate_id]["status"] == "rejected_for_import"
    assert candidates[second_candidate_id]["reviewed_payload"] is None

    assert accepted.status_code == 200
    assert accepted.json()["review_batch"]["status"] == "ready_to_import"


def test_review_batch_draft_returns_persisted_gate_for_edited_candidate_name(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        review_batch_id = submission["review_batch"]["id"]

        saved = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": submission["candidates"][0]["id"],
                        "included": True,
                        "reviewed_payload": {
                            "line_type": "material",
                            "name": "PVC pressure pipe",
                            "top_level_category": "Plumbing",
                            "subcategory": "Pipes",
                            "quantity": "20",
                            "unit": "pcs",
                            "price": "1500",
                            "provider_name": "ABC Trading",
                        },
                    }
                ]
            },
        )
        assert saved.status_code == 200
        gate = saved.json()["candidates"][0]["taxonomy_gates"][0]
        assert gate["subject_name"] == "PVC pressure pipe"

        drafted = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate['id']}/reviewer-draft",
            json={
                "top_level_category": "Plumbing",
                "subcategory": "Pressure Pipes",
            },
        )
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate['id']}/accept"
        )

    assert drafted.status_code == 200
    assert accepted.status_code == 200
    accepted_gate = accepted.json()["candidates"][0]["taxonomy_gates"][0]
    assert accepted_gate["id"] == gate["id"]
    assert accepted_gate["status"] == "accepted"
    assert accepted_gate["accepted_category_path"] == "Plumbing / Pressure Pipes"


def test_review_batch_draft_rejects_included_candidate_without_category_path(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)

        response = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": submission["candidates"][0]["id"],
                        "included": True,
                        "reviewed_payload": {
                            "line_type": "material",
                            "name": "PVC pipe",
                            "top_level_category": "Plumbing",
                            "quantity": "20",
                        },
                    }
                ]
            },
        )
        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        ).json()

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Included candidates require valid linked concepts and resolved category paths"
    )
    assert batch["candidates"][0]["decision"] is None
    assert batch["review_batch"]["status"] == "review_pending"


def test_review_batch_draft_rejects_missing_candidate_from_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "material", "name": "PVC elbow"},
        )

        response = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": submission["candidates"][0]["id"],
                        "included": False,
                        "reviewed_payload": None,
                    }
                ]
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Review draft must include every candidate in the Review Batch"


def create_manual_submission(client: TestClient):
    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "contractor_assigned": "Internal",
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
            "category_suggestion": {
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
            },
        },
    )
    return project, submission


def add_candidate_to_batch(
    client: TestClient,
    *,
    project_workspace_id: int,
    review_batch_id: int,
    source_submission_id: int,
    proposed_payload: dict,
) -> int:
    from backend.app.review.models import ExtractedCandidate

    with client.app.state.session_factory() as session:
        candidate = ExtractedCandidate(
            project_workspace_id=project_workspace_id,
            review_batch_id=review_batch_id,
            source_submission_id=source_submission_id,
            status="pending_review",
            proposed_payload=proposed_payload,
        )
        session.add(candidate)
        session.commit()
        return candidate.id
