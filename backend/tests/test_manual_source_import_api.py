import os

from fastapi.testclient import TestClient


def make_client(tmp_path):
    os.environ["HABI_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'habi_test.db'}"

    from backend.app.main import create_app

    return TestClient(create_app())


def test_manual_source_entry_creates_pending_candidate_outside_active_purchase_lines(tmp_path):
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

        submission = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={
                "line_type": "material",
                "name": "PVC pipe",
                "quantity": "20",
                "unit": "pcs",
                "price": "1500",
                "currency": "PHP",
                "provider_name": "ABC Trading",
                "purchase_date": "2025-07-12",
                "remarks_or_terms": "Delivery included",
            },
        )

        purchase_lines = client.get(
            f"/api/project-workspaces/{project['id']}/purchase-lines"
        )

    assert submission.status_code == 201
    assert submission.json()["review_batch"]["status"] == "review_pending"
    assert submission.json()["candidate"]["status"] == "pending_review"
    assert purchase_lines.status_code == 200
    assert purchase_lines.json()["items"] == []


def test_approved_manual_candidate_imports_active_purchase_line_with_evidence(tmp_path):
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

        decision = client.post(
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
        imported = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )
        purchase_lines = client.get(
            f"/api/project-workspaces/{project['id']}/purchase-lines"
        )

    assert decision.status_code == 200
    assert imported.status_code == 200
    assert purchase_lines.json()["items"] == [
        {
            "id": imported.json()["imported_purchase_lines"][0]["id"],
            "item_or_service_name": "PVC pipe",
            "line_type": "material",
            "provider_name": "ABC Trading",
            "provider_type": "external",
            "provider_role": "material_supplier",
            "quantity": "20",
            "unit": "pcs",
            "unit_state": "known",
            "price": "1500",
            "currency": "PHP",
            "price_state": "known",
            "purchase_date": "2025-07-12",
            "date_state": "known",
            "category_path": "Plumbing / Pipes",
            "has_evidence": True,
            "source_label": "Manual Source Entry",
        }
    ]


def test_review_batch_status_reaches_ready_only_after_complete_importable_review(tmp_path):
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
        extra_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            manual_source_entry_id=submission["manual_source_entry"]["id"],
            proposed_payload={
                "line_type": "service",
                "name": "Hauling",
                "quantity": "1",
                "unit": "lot",
                "price": "2500",
                "provider_name": "ABC Trading",
            },
        )

        first_decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidate']['id']}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Plumbing",
                    "subcategory": "",
                    "quantity": "20",
                    "unit": "pcs",
                    "price": "1500",
                    "provider_name": "ABC Trading",
                    "purchase_date": "2025-07-12",
                },
            },
        )
        after_first_decision = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

        rejection = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{extra_candidate_id}/decision",
            json={"decision": "rejected", "reviewed_payload": None},
        )
        after_rejection = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

        corrected_decision = client.post(
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
                    "provider_name": "ABC Trading",
                    "purchase_date": "2025-07-12",
                },
            },
        )
        after_correction = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert first_decision.status_code == 200
    assert after_first_decision.json()["review_batch"]["status"] == "review_in_progress"
    assert rejection.status_code == 200
    assert after_rejection.json()["review_batch"]["status"] == "review_in_progress"
    assert corrected_decision.status_code == 200
    assert after_correction.json()["review_batch"]["status"] == "ready_to_import"


def test_manual_import_preserves_unknown_states_and_project_scope(tmp_path):
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
        other_project = client.post(
            "/api/project-workspaces",
            json={
                "project_name": "Ortigas Office Fit-Out",
                "project_type": "Commercial fit-out",
                "location": "Pasig City",
                "completion_year": 2024,
            },
        ).json()
        submission = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={
                "line_type": "service",
                "name": "Concrete coring",
                "quantity": "1",
                "unit": "",
                "price": "",
                "provider_name": "",
                "remarks_or_terms": "Night work",
            },
        ).json()

        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidate']['id']}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "service",
                    "name": "Concrete coring",
                    "top_level_category": "Civil",
                    "subcategory": "Coring",
                    "quantity": "1",
                    "unit": "",
                    "price": "",
                    "currency": "",
                    "provider_name": "",
                    "purchase_date": None,
                    "remarks_or_terms": "Night work",
                },
            },
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )
        purchase_lines = client.get(
            f"/api/project-workspaces/{project['id']}/purchase-lines"
        )
        other_purchase_lines = client.get(
            f"/api/project-workspaces/{other_project['id']}/purchase-lines"
        )

    assert purchase_lines.status_code == 200
    assert purchase_lines.json()["items"][0] == {
        "id": purchase_lines.json()["items"][0]["id"],
        "item_or_service_name": "Concrete coring",
        "line_type": "service",
        "provider_name": None,
        "provider_type": "unknown",
        "provider_role": None,
        "quantity": "1",
        "unit": None,
        "unit_state": "unknown",
        "price": None,
        "currency": None,
        "price_state": "unknown",
        "purchase_date": None,
        "date_state": "unknown",
        "category_path": "Civil / Coring",
        "has_evidence": True,
        "source_label": "Manual Source Entry",
    }
    assert other_purchase_lines.status_code == 200
    assert other_purchase_lines.json()["items"] == []


def add_candidate_to_batch(
    client: TestClient,
    *,
    project_workspace_id: int,
    review_batch_id: int,
    manual_source_entry_id: int,
    proposed_payload: dict,
) -> int:
    from backend.app.review.models import ExtractedCandidate

    with client.app.state.session_factory() as session:
        candidate = ExtractedCandidate(
            project_workspace_id=project_workspace_id,
            review_batch_id=review_batch_id,
            manual_source_entry_id=manual_source_entry_id,
            status="pending_review",
            proposed_payload=proposed_payload,
        )
        session.add(candidate)
        session.commit()
        return candidate.id
