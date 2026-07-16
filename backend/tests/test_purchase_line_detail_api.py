from sqlalchemy import select

from backend.app.evidence.models import EvidenceAnnotation, EvidenceRecord
from backend.app.processing.worker import run_once
from backend.tests.manual_submission_helpers import (
    accept_all_taxonomy_gates,
    create_review_ready_manual_submission,
)


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
        {**reviewed_annotation, "target_concept_id": None},
        {**grounded_reviewer_annotation, "target_concept_id": None},
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
            "concept_key": None,
            "quantity": None,
            "unit": None,
            "component_unit_price": None,
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
            "source_locator": None,
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
    assert source_evidence["locator"] == evidence["locator"]
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

    with client.app.state.session_factory() as session, session.begin():
        annotations = list(
            session.scalars(select(EvidenceAnnotation).order_by(EvidenceAnnotation.id))
        )
        annotations[0].source_locator = {"kind": "text_span", "start": -1, "end": -1}
        annotations[1].source_locator = {
            "kind": "xlsx_cell",
            "worksheet": "Purchases",
            "coordinate": "",
        }

    damaged_locator_detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_line_id}"
    )
    assert damaged_locator_detail.status_code == 200
    assert damaged_locator_detail.json()["evidence_records"][0]["locator"] == {
        "kind": "structured_manual"
    }
    assert [
        annotation["source_locator"]
        for annotation in damaged_locator_detail.json()["evidence_records"][0][
            "annotations"
        ]
    ] == [None, None]

    with client.app.state.session_factory() as session, session.begin():
        evidence_record = session.get(EvidenceRecord, evidence["id"])
        annotations = list(
            session.scalars(select(EvidenceAnnotation).order_by(EvidenceAnnotation.id))
        )
        evidence_record.content = {"original_text": "Short source text"}
        annotations[0].source_locator = {
            "kind": "text_span",
            "start": 6,
            "end": 12,
        }
        annotations[1].source_locator = {
            "kind": "structured_field",
            "field_path": "structured_payload.not_a_real_source_path",
        }

    missing_text_and_field_detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_line_id}"
    )
    assert missing_text_and_field_detail.status_code == 200
    assert missing_text_and_field_detail.json()["evidence_records"][0]["locator"] == {
        "kind": "manual_text",
        "field_path": "original_text",
    }
    assert [
        annotation["source_locator"]
        for annotation in missing_text_and_field_detail.json()["evidence_records"][0][
            "annotations"
        ]
    ] == [None, None]

    with client.app.state.session_factory() as session, session.begin():
        evidence_record = session.get(EvidenceRecord, evidence["id"])
        evidence_record.content = {
            "worksheet": "Purchases",
            "locators": [{"row": 2, "role": "body"}],
            "row_snapshot": [
                {
                    "column": 1,
                    "coordinate": "A2",
                    "header": "Item",
                    "value": "PVC pipe",
                    "annotation": False,
                }
            ],
        }
        annotations = list(
            session.scalars(select(EvidenceAnnotation).order_by(EvidenceAnnotation.id))
        )
        annotations[0].source_locator = {
            "kind": "xlsx_cell",
            "worksheet": "Purchases",
            "coordinate": "Z999",
        }

    missing_cell_detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_line_id}"
    )
    assert missing_cell_detail.status_code == 200
    assert missing_cell_detail.json()["evidence_records"][0]["locator"] == {
        "kind": "xlsx_rows",
        "worksheet": "Purchases",
        "rows": [{"row": 2, "role": "body"}],
    }

    from backend.app.memory.models import MemoryRecord, PurchaseLine

    with client.app.state.session_factory() as session, session.begin():
        purchase_line = session.get(PurchaseLine, purchase_line_id)
        session.get(MemoryRecord, purchase_line.memory_record_id).status = "archived"

    archived_detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_line_id}"
    )
    active_grid = client.get(f"/api/project-workspaces/{project['id']}/purchase-lines")
    assert archived_detail.status_code == 200
    assert archived_detail.json()["status"] == "archived"
    assert active_grid.json()["items"] == []


def test_all_annotation_types_and_valid_targets_import_on_their_original_evidence(client):
    project = _create_project(client)
    annotation_types = [
        "delivery_terms",
        "payment_terms",
        "validity_terms",
        "warranty_terms",
        "availability_terms",
        "condition_or_exclusion",
        "general_qualifier",
    ]
    targets = [
        "purchase_line",
        "material",
        "service",
        "provider",
        "purchase_line",
        "service",
        "material",
    ]
    source_annotations = [
        {
            "text": f"Source qualifier {index}",
            "annotation_type": annotation_type,
            "target": target,
        }
        for index, (annotation_type, target) in enumerate(
            zip(annotation_types, targets, strict=True)
        )
    ]
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={
            "line_type": "material",
            "name": "PVC pipe",
            "annotations": source_annotations,
        },
    )
    candidate_id = submission["candidates"][0]["id"]
    review_batch_id = submission["review_batch"]["id"]
    proposals = [
        {
            "proposal_id": f"structured:annotations:{index}",
            "text": annotation["text"],
            "annotation_type": annotation["annotation_type"],
            "target": annotation["target"],
            "source_excerpt": annotation["text"],
            "source_locator": {
                "kind": "structured_field",
                "field_path": f"structured_payload.annotations[{index}].text",
            },
            "provenance": "source_field",
        }
        for index, annotation in enumerate(source_annotations)
    ]
    with client.app.state.session_factory() as session, session.begin():
        from backend.app.review.models import ExtractedCandidate

        candidate = session.get(ExtractedCandidate, candidate_id)
        candidate.proposed_payload = {
            "linked_concepts": [
                {
                    "concept_type": "material",
                    "name": "PVC pipe",
                    "category_suggestion": {
                        "top_level_category": "Plumbing",
                        "subcategory": "Pipes",
                    },
                },
                {
                    "concept_type": "service",
                    "name": "PVC pipe installation",
                    "category_suggestion": {
                        "top_level_category": "Trade services",
                        "subcategory": "Pipe installation",
                    },
                },
            ],
            "provider_state": "external",
            "provider_name": "ABC Trading",
            "provider_category_suggestion": {
                "top_level_category": "Providers",
                "subcategory": "General",
            },
            "annotation_proposals": proposals,
        }

    reviewed_payload = {
        "linked_concepts": [
            {
                "concept_type": "material",
                "name": "PVC pipe",
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
            },
            {
                "concept_type": "service",
                "name": "PVC pipe installation",
                "top_level_category": "Trade services",
                "subcategory": "Pipe installation",
            },
        ],
        "provider_state": "external",
        "provider_name": "ABC Trading",
        "provider_top_level_category": "Providers",
        "provider_subcategory": "General",
        "annotation_proposals": proposals,
    }
    decision = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}/"
        f"candidates/{candidate_id}/decision",
        json={"decision": "approved", "reviewed_payload": reviewed_payload},
    )
    assert decision.status_code == 200, decision.json()
    accept_all_taxonomy_gates(
        client,
        project_workspace_id=project["id"],
        review_batch_id=review_batch_id,
    )
    imported = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}/import"
    )
    assert imported.status_code == 200, imported.json()
    purchase_line_id = imported.json()["imported_purchase_lines"][0]["id"]
    annotations = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_line_id}"
    ).json()["evidence_records"][0]["annotations"]

    assert [annotation["annotation_type"] for annotation in annotations] == annotation_types
    assert {annotation["target"]["record_type"] for annotation in annotations} == {
        "purchase_line",
        "material",
        "service",
        "provider",
    }


def test_free_form_annotations_have_no_count_cap_through_import_and_detail(client):
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
    assert len(candidate["proposed_payload"]["annotation_proposals"]) == 21
    assert "annotation_omitted_count" not in candidate["proposed_payload"]
    assert "warning_summary" not in job["diagnostics"]

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
    assert evidence["annotation_omitted_count"] == 0
    assert evidence["annotation_detected_count"] == 0
    assert len(evidence["annotations"]) == 21

    source_detail = client.get(
        f"/api/project-workspaces/{project['id']}/source-submissions/"
        f"{submission['source_submission']['id']}"
    ).json()
    assert source_detail["imported_evidence"][0]["annotation_omitted_count"] == 0
    assert source_detail["imported_evidence"][0]["annotation_detected_count"] == 0
