from fastapi.testclient import TestClient

from backend.tests.db import make_postgres_test_client


def make_client(_tmp_path):
    return make_postgres_test_client()


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
                "entry_type": "structured_row",
                "structured_payload": {
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
            },
        )

        purchase_lines = client.get(
            f"/api/project-workspaces/{project['id']}/purchase-lines"
        )

    submission_body = submission.json()
    assert submission.status_code == 201
    assert submission_body["source_submission"]["submission_type"] == "manual_source_entry"
    assert submission_body["manual_source_entry"]["source_submission_id"] == submission_body["source_submission"]["id"]
    assert submission_body["manual_source_entry"]["entry_type"] == "structured_row"
    assert submission_body["processing_job"]["status"] == "review_ready"
    assert submission_body["processing_job"]["source_submission_id"] == submission_body["source_submission"]["id"]
    assert submission_body["processing_job"]["candidate_count"] == 1
    assert submission_body["processing_job"]["review_batch_id"] == submission_body["review_batch"]["id"]
    assert submission_body["review_batch"]["source_submission_id"] == submission_body["source_submission"]["id"]
    assert len(submission_body["candidates"]) == 1
    assert submission_body["candidates"][0]["status"] == "pending_review"
    assert submission_body["candidates"][0]["source_submission_id"] == submission_body["source_submission"]["id"]
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
            json=structured_manual_entry_payload(
                line_type="material",
                name="PVC pipe",
                quantity="20",
                unit="pcs",
                price="1500",
                provider_name="ABC Trading",
                purchase_date="2025-07-12",
                remarks_or_terms="Delivery included",
            ),
        ).json()

        decision = client.post(
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


def test_useful_free_form_manual_source_entry_creates_reviewable_candidate(tmp_path):
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
                "entry_type": "free_form_text",
                "original_text": "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500",
            },
        )

    submission_body = submission.json()
    candidate_payload = submission_body["candidates"][0]["proposed_payload"]
    assert submission.status_code == 201
    assert submission_body["manual_source_entry"]["entry_type"] == "free_form_text"
    assert (
        submission_body["manual_source_entry"]["original_text"]
        == "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
    )
    assert submission_body["manual_source_entry"]["structured_payload"] is None
    assert submission_body["processing_job"]["status"] == "review_ready"
    assert submission_body["processing_job"]["candidate_count"] == 1
    assert submission_body["processing_job"]["review_batch_id"] == submission_body["review_batch"]["id"]
    assert candidate_payload["raw_text"] == "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
    assert candidate_payload["line_type"] == "material"
    assert candidate_payload["name"] == "PVC pipe"
    assert candidate_payload["quantity"] == "20"
    assert candidate_payload["unit"] == "pcs"
    assert candidate_payload["price"] == "1500"
    assert candidate_payload["currency"] == "PHP"
    assert candidate_payload["provider_name"] == "ABC Trading"
    assert candidate_payload["confidence"] > 0
    assert candidate_payload["category_suggestion"] == {
        "top_level_category": "Plumbing",
        "subcategory": "Pipes",
    }
    assert candidate_payload["evidence"] == {
        "source_submission_id": submission_body["source_submission"]["id"],
        "snippet": "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500",
        "locator": "manual_source_entry.original_text",
    }


def test_approved_free_form_candidate_imports_purchase_line_with_original_text_evidence(tmp_path):
    original_text = "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
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
            json={"entry_type": "free_form_text", "original_text": original_text},
        ).json()
        candidate = submission["candidates"][0]

        decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{candidate['id']}/decision",
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
                    "purchase_date": None,
                    "remarks_or_terms": None,
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
    evidence_contents = imported_purchase_line_evidence_contents(
        client,
        imported.json()["imported_purchase_lines"][0]["id"],
    )
    assert purchase_lines.json()["items"][0]["item_or_service_name"] == "PVC pipe"
    assert purchase_lines.json()["items"][0]["has_evidence"] is True
    assert evidence_contents == [{"original_text": original_text}]


def test_unusable_free_form_manual_source_entry_creates_no_candidates(tmp_path):
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
                "entry_type": "free_form_text",
                "original_text": "Follow up with foreman after inspection.",
            },
        )

    submission_body = submission.json()
    assert submission.status_code == 201
    assert submission_body["source_submission"]["submission_type"] == "manual_source_entry"
    assert submission_body["manual_source_entry"]["original_text"] == "Follow up with foreman after inspection."
    assert submission_body["processing_job"]["status"] == "no_candidates_found"
    assert submission_body["processing_job"]["candidate_count"] == 0
    assert submission_body["processing_job"]["review_batch_id"] is None
    assert submission_body["review_batch"] is None
    assert submission_body["candidates"] == []


def test_blank_free_form_manual_source_entry_is_rejected_before_source_submission(tmp_path):
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

        rejected = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": "   "},
        )
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json=structured_manual_entry_payload(
                line_type="material",
                name="PVC pipe",
            ),
        )

    assert rejected.status_code == 422
    assert accepted.status_code == 201
    assert accepted.json()["source_submission"]["id"] == 1


def test_overlong_free_form_manual_source_entry_is_rejected_before_source_submission(tmp_path):
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

        rejected = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": "x" * 10001},
        )
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json=structured_manual_entry_payload(
                line_type="material",
                name="PVC pipe",
            ),
        )

    assert rejected.status_code == 422
    assert accepted.status_code == 201
    assert accepted.json()["source_submission"]["id"] == 1


def test_processing_job_status_endpoint_returns_project_scoped_job_detail(tmp_path):
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
                "entry_type": "free_form_text",
                "original_text": "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500",
            },
        ).json()

        job_detail = client.get(
            f"/api/project-workspaces/{project['id']}/processing-jobs/{submission['processing_job']['id']}"
        )
        cross_project_detail = client.get(
            f"/api/project-workspaces/{other_project['id']}/processing-jobs/{submission['processing_job']['id']}"
        )

    assert job_detail.status_code == 200
    assert job_detail.json()["processing_job"]["id"] == submission["processing_job"]["id"]
    assert job_detail.json()["processing_job"]["status"] == "review_ready"
    assert job_detail.json()["source_submission"] == {
        "id": submission["source_submission"]["id"],
        "submission_type": "manual_source_entry",
        "submitted_at": submission["source_submission"]["submitted_at"],
    }
    assert job_detail.json()["review_batch_id"] == submission["review_batch"]["id"]
    assert cross_project_detail.status_code == 404


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
            json=structured_manual_entry_payload(
                line_type="material",
                name="PVC pipe",
                quantity="20",
                unit="pcs",
                price="1500",
                provider_name="ABC Trading",
                purchase_date="2025-07-12",
                remarks_or_terms="Delivery included",
            ),
        ).json()
        extra_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
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
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
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
            json=structured_manual_entry_payload(
                line_type="service",
                name="Concrete coring",
                quantity="1",
                unit="",
                price="",
                provider_name="",
                remarks_or_terms="Night work",
            ),
        ).json()

        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
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


def structured_manual_entry_payload(**structured_payload: object) -> dict:
    return {
        "entry_type": "structured_row",
        "structured_payload": structured_payload,
    }


def imported_purchase_line_evidence_contents(
    client: TestClient,
    purchase_line_id: int,
) -> list[dict]:
    from sqlalchemy import select

    from backend.app.evidence.models import EvidenceRecord, MemoryRecordEvidenceLink
    from backend.app.memory.models import PurchaseLine

    with client.app.state.session_factory() as session:
        purchase_line = session.get(PurchaseLine, purchase_line_id)
        return list(
            session.scalars(
                select(EvidenceRecord.content)
                .join(
                    MemoryRecordEvidenceLink,
                    MemoryRecordEvidenceLink.evidence_record_id == EvidenceRecord.id,
                )
                .where(MemoryRecordEvidenceLink.memory_record_id == purchase_line.memory_record_id)
                .order_by(EvidenceRecord.id)
            )
        )
