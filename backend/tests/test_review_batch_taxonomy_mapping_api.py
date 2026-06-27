from fastapi.testclient import TestClient

from backend.tests.db import make_postgres_test_client
from backend.tests.manual_submission_helpers import create_review_ready_manual_submission


def make_client(_tmp_path):
    return make_postgres_test_client()


def test_review_taxonomy_mapping_updates_all_matching_candidates_in_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "material",
                "name": "PVC elbow",
                "quantity": "10",
                "unit": "pcs",
                "category_suggestion": {
                    "top_level_category": " mechanical ",
                    "subcategory": "PIPE   MATERIALS",
                },
            },
        )
        unrelated_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "service",
                "name": "Hauling",
                "category_suggestion": {
                    "top_level_category": "Services",
                    "subcategory": "Hauling",
                },
            },
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-mappings",
            json={
                "candidate_id": first_candidate_id,
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
                "apply_to_similar": True,
            },
        )

    assert response.status_code == 200
    candidates = {candidate["id"]: candidate for candidate in response.json()["candidates"]}
    assert candidates[first_candidate_id]["reviewed_payload"]["top_level_category"] == "Plumbing"
    assert candidates[first_candidate_id]["reviewed_payload"]["subcategory"] == "Pipes"
    assert candidates[second_candidate_id]["reviewed_payload"]["top_level_category"] == "Plumbing"
    assert candidates[second_candidate_id]["reviewed_payload"]["subcategory"] == "Pipes"
    assert candidates[unrelated_candidate_id]["reviewed_payload"] is None
    decisions = response.json()["taxonomy_decisions"]
    assert decisions[-1]["decision"] == "mapped"
    assert decisions[-1]["suggested_top_level_category"] == "Mechanical"
    assert decisions[-1]["suggested_subcategory"] == "Pipe Materials"


def test_review_taxonomy_mapping_accepts_trimmed_custom_path(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        candidate_id = submission["candidates"][0]["id"]

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-mappings",
            json={
                "candidate_id": candidate_id,
                "top_level_category": "  Custom Plumbing  ",
                "subcategory": "  Specialty Pipes  ",
                "apply_to_similar": False,
            },
        )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["reviewed_payload"]["top_level_category"] == "Custom Plumbing"
    assert candidate["reviewed_payload"]["subcategory"] == "Specialty Pipes"
    decisions = response.json()["taxonomy_decisions"]
    assert decisions[-1]["decision"] == "mapped"


def test_review_taxonomy_mapping_accepts_custom_path_without_ai_suggestion(tmp_path):
    with make_client(tmp_path) as client:
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
            },
        )
        candidate_id = submission["candidates"][0]["id"]

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-mappings",
            json={
                "candidate_id": candidate_id,
                "top_level_category": "Custom Plumbing",
                "subcategory": "Specialty Pipes",
                "apply_to_similar": False,
            },
        )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["reviewed_payload"]["top_level_category"] == "Custom Plumbing"
    assert candidate["reviewed_payload"]["subcategory"] == "Specialty Pipes"
    assert response.json()["taxonomy_decisions"][-1]["decision"] == "mapped"


def test_review_taxonomy_mapping_rejects_terminal_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        candidate_id = submission["candidates"][0]["id"]
        client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": candidate_id,
                        "included": True,
                        "reviewed_payload": {
                            "line_type": "material",
                            "name": "PVC pipe",
                            "top_level_category": "Plumbing",
                            "subcategory": "Pipes",
                        },
                    }
                ]
            },
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-mappings",
            json={
                "candidate_id": candidate_id,
                "top_level_category": "Plumbing",
                "subcategory": "Pipe Materials",
                "apply_to_similar": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Terminal review batches cannot be changed"


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
            "category_suggestion": {
                "top_level_category": "Mechanical",
                "subcategory": "Pipe Materials",
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
