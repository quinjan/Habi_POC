from sqlalchemy import select

from backend.app.evidence.models import EvidenceAnnotation
from backend.app.processing.worker import run_once
from backend.tests.manual_submission_helpers import accept_all_taxonomy_gates


def _create_project(client, name="Arnaiz Residence Renovation"):
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


def test_reviewed_annotation_imports_and_appears_in_purchase_line_detail(client):
    project = _create_project(client)
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
                "annotations": [
                    {
                        "text": "Delivery included",
                        "annotation_type": "delivery_terms",
                        "target": "purchase_line",
                    }
                ],
            },
        },
    ).json()
    assert run_once(client.app.state.session_factory) == 1
    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()
    candidate = review["candidates"][0]
    proposed_annotation = candidate["proposed_payload"]["annotation_proposals"][0]
    reviewed_annotation = {
        **proposed_annotation,
        "text": "Five-year delivery warranty",
        "annotation_type": "warranty_terms",
        "target": "material",
    }

    tampered = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job['review_batch_id']}/candidates/{candidate['id']}/decision",
        json={
            "decision": "approved",
            "reviewed_payload": {
                "line_type": "material",
                "name": "PVC pipe",
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
                "provider_state": "unknown",
                "annotation_proposals": [
                    {**reviewed_annotation, "source_excerpt": "Invented source text"}
                ],
            },
        },
    )
    assert tampered.status_code == 400
    assert tampered.json()["detail"] == "Annotation source grounding is immutable"

    fabricated_reviewer_annotation = {
        "proposal_id": "reviewer:1",
        "text": "Reviewer invented this qualifier",
        "annotation_type": "general_qualifier",
        "target": "purchase_line",
        "source_excerpt": "Reviewer-added annotation",
        "source_locator": {"kind": "reviewer_entry"},
        "provenance": "reviewer_added",
    }
    fabricated = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job['review_batch_id']}/candidates/{candidate['id']}/decision",
        json={
            "decision": "approved",
            "reviewed_payload": {
                "line_type": "material",
                "name": "PVC pipe",
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
                "provider_state": "unknown",
                "annotation_proposals": [fabricated_reviewer_annotation],
            },
        },
    )
    assert fabricated.status_code == 400
    assert fabricated.json()["detail"] == (
        "Reviewer-added annotations must quote and locate preserved source content"
    )

    grounded_reviewer_annotation = {
        **fabricated_reviewer_annotation,
        "source_excerpt": "Delivery included",
        "source_locator": {
            "kind": "structured_field",
            "field_path": "structured_payload.annotations[0].text",
        },
    }

    saved = client.put(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job['review_batch_id']}/review-draft",
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
                        "provider_state": "unknown",
                        "annotation_proposals": [
                            reviewed_annotation,
                            grounded_reviewer_annotation,
                        ],
                    },
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.json()
    assert saved.json()["candidates"][0]["reviewed_payload"]["annotation_proposals"] == [
        reviewed_annotation,
        grounded_reviewer_annotation,
    ]

    accept_all_taxonomy_gates(
        client,
        project_workspace_id=project["id"],
        review_batch_id=job["review_batch_id"],
    )
    imported = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job['review_batch_id']}/import"
    )
    assert imported.status_code == 200, imported.json()
    purchase_line_id = imported.json()["imported_purchase_lines"][0]["id"]

    with client.app.state.session_factory() as session, session.begin():
        first_annotation = session.scalars(
            select(EvidenceAnnotation).order_by(EvidenceAnnotation.id)
        ).first()
        first_annotation.source_locator = {"kind": "manual_text"}

    detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_line_id}"
    )

    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == purchase_line_id
    assert body["status"] == "active"
    assert body["linked_concepts"] == [
        {
            "memory_record_id": body["linked_concepts"][0]["memory_record_id"],
            "concept_type": "material",
            "name": "PVC pipe",
            "category_path": "Plumbing / Pipes",
        }
    ]
    assert body["provider"] == {"state": "unknown", "record": None, "roles": []}
    assert body["value_history_available"] is False
    assert len(body["evidence_records"]) == 1
    evidence = body["evidence_records"][0]
    assert evidence["source_submission_id"] == submission["source_submission"]["id"]
    assert evidence["source_label"] == "Manual Source Entry"
    assert evidence["source_type"] == "structured_row"
    assert evidence["source_submission_href"] == (
        f"/projects/{project['id']}/sources/{submission['source_submission']['id']}"
    )
    assert evidence["locator"] == {
        "kind": "structured_field",
        "field_path": "structured_payload.annotations[0].text",
    }
    assert evidence["annotations"] == [
        {
            "id": evidence["annotations"][0]["id"],
            "proposal_id": "structured:annotations:0",
            "text": "Five-year delivery warranty",
            "annotation_type": "warranty_terms",
            "target": {
                "memory_record_id": body["linked_concepts"][0]["memory_record_id"],
                "record_type": "material",
                "name": "PVC pipe",
            },
            "source_excerpt": "Delivery included",
            "source_locator": {
                "kind": "manual_text",
            },
            "provenance": "source_field",
        },
        {
            "id": evidence["annotations"][1]["id"],
            "proposal_id": "reviewer:1",
            "text": "Reviewer invented this qualifier",
            "annotation_type": "general_qualifier",
            "target": {
                "memory_record_id": evidence["annotations"][1]["target"][
                    "memory_record_id"
                ],
                "record_type": "purchase_line",
                "name": "PVC pipe",
            },
            "source_excerpt": "Delivery included",
            "source_locator": {
                "kind": "structured_field",
                "field_path": "structured_payload.annotations[0].text",
            },
            "provenance": "reviewer_added",
        },
    ]

    source_detail = client.get(
        f"/api/project-workspaces/{project['id']}/source-submissions/"
        f"{submission['source_submission']['id']}"
    ).json()
    assert source_detail["processing_job"]["status"] == "completed"
    assert source_detail["review_batch"] == {
        "id": job["review_batch_id"],
        "status": "imported",
        "href": (
            f"/projects/{project['id']}/review-batches/{job['review_batch_id']}"
        ),
    }
    assert source_detail["empty_state"] is None
    assert len(source_detail["imported_evidence"]) == 1
    source_evidence = source_detail["imported_evidence"][0]
    assert source_evidence["id"] == evidence["id"]
    assert source_evidence["annotations"] == evidence["annotations"]
    assert source_evidence["purchase_lines"] == [
        {
            "id": purchase_line_id,
            "status": "active",
            "href": f"/projects/{project['id']}/purchase-lines/{purchase_line_id}",
            "linked_records": [
                {
                    "memory_record_id": body["linked_concepts"][0]["memory_record_id"],
                    "record_type": "material",
                    "name": "PVC pipe",
                    "category_path": "Plumbing / Pipes",
                }
            ],
        }
    ]


def test_free_form_annotation_limit_warning_persists_through_import_and_detail(client):
    class TwentyOneAnnotationProvider:
        def extract_purchase_lines(self, *, original_text, source_submission_id):
            return {
                "candidates": [
                    {
                        "line_type": "material",
                        "name": "PVC pipe",
                        "category_suggestion": {
                            "top_level_category": "Plumbing",
                            "subcategory": "Pipes",
                        },
                        "provider_state": "unknown",
                        "confidence": 0.9,
                        "evidence": {
                            "source_submission_id": source_submission_id,
                            "locator": "manual_source_entry.original_text",
                        },
                        "annotation_proposals": [
                            {
                                "text": f"Qualifier {index:02d}",
                                "annotation_type": "general_qualifier",
                                "target": "purchase_line",
                                "source_excerpt": f"Qualifier {index:02d}",
                            }
                            for index in range(1, 22)
                        ],
                    }
                ]
            }

    original_text = ". ".join(f"Qualifier {index:02d}" for index in range(1, 22))
    project = _create_project(client)
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={"entry_type": "free_form_text", "original_text": original_text},
    ).json()
    assert (
        run_once(
            client.app.state.session_factory,
            ai_provider=TwentyOneAnnotationProvider(),
        )
        == 1
    )
    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()
    candidate = review["candidates"][0]
    assert len(candidate["proposed_payload"]["annotation_proposals"]) == 20
    assert candidate["proposed_payload"]["annotation_omitted_count"] == 1
    assert candidate["proposed_payload"]["annotation_detected_count"] == 21
    assert "Annotation extraction limit reached" in job["diagnostics"]["warning_summary"]

    saved = client.put(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job['review_batch_id']}/review-draft",
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
                        "provider_state": "unknown",
                        "annotation_proposals": candidate["proposed_payload"][
                            "annotation_proposals"
                        ],
                    },
                }
            ]
        },
    )
    assert saved.status_code == 200, saved.json()
    accept_all_taxonomy_gates(
        client,
        project_workspace_id=project["id"],
        review_batch_id=job["review_batch_id"],
    )
    imported = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job['review_batch_id']}/import"
    ).json()
    purchase_line_id = imported["imported_purchase_lines"][0]["id"]
    detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_line_id}"
    ).json()
    evidence = detail["evidence_records"][0]
    assert evidence["annotation_omitted_count"] == 1
    assert evidence["annotation_detected_count"] == 21
    assert len(evidence["annotations"]) == 20

    source_detail = client.get(
        f"/api/project-workspaces/{project['id']}/source-submissions/"
        f"{submission['source_submission']['id']}"
    ).json()
    assert source_detail["imported_evidence"][0]["annotation_omitted_count"] == 1
    assert source_detail["imported_evidence"][0]["annotation_detected_count"] == 21
