from backend.tests.manual_submission_helpers import (
    accept_all_taxonomy_gates,
    create_review_ready_manual_submission,
)


def _create_project(
    client,
    *,
    name: str = "Arnaiz Residence Renovation",
    contractor_assigned: str = "Quinlan Construction",
) -> dict:
    response = client.post(
        "/api/project-workspaces",
        json={
            "project_name": name,
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "contractor_assigned": contractor_assigned,
        },
    )
    assert response.status_code == 201
    return response.json()


def _import_reviewed_line(client, project: dict, reviewed_payload: dict) -> dict:
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={
            "line_type": "material",
            "name": "PVC pipe",
            "top_level_category": "Plumbing",
            "subcategory": "Pipes",
        },
    )
    candidate_id = submission["candidates"][0]["id"]
    review_batch_id = submission["review_batch"]["id"]

    decision = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}/candidates/{candidate_id}/decision",
        json={
            "decision": "approved",
            "reviewed_payload": reviewed_payload,
        },
    )
    assert decision.status_code == 200
    accept_all_taxonomy_gates(
        client,
        project_workspace_id=project["id"],
        review_batch_id=review_batch_id,
    )
    batch = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}"
    )
    assert batch.json()["review_batch"]["status"] == "ready_to_import"
    imported = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}/import"
    )
    assert imported.status_code == 200, imported.json()
    return imported.json()


def _import_bundled_line(client, project: dict) -> dict:
    return _import_reviewed_line(
        client,
        project,
        {
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
                "quantity": "20",
                "unit": "pcs",
                "price": "1500",
                "currency": "PHP",
                "purchase_date": "2025-07-12",
        },
    )


def _add_candidate(
    client,
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


def test_reviewer_imports_one_bundled_purchase_line_with_two_linked_concepts(client):
    project = _create_project(client)
    imported = _import_bundled_line(client, project)
    purchase_lines = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines"
    )

    assert purchase_lines.status_code == 200
    assert purchase_lines.json()["items"] == [
        {
            "id": imported["imported_purchase_lines"][0]["id"],
            "line_type": "bundled",
            "linked_concepts": [
                {
                    "memory_record_id": 1,
                    "concept_type": "material",
                    "name": "PVC pipe",
                    "category_path": "Plumbing / Pipes",
                },
                {
                    "memory_record_id": 2,
                    "concept_type": "service",
                    "name": "PVC pipe installation",
                    "category_path": "Trade services / Pipe installation",
                },
            ],
            "provider_state": "external",
            "provider_name": "ABC Trading",
            "provider_category_path": "Providers / General",
            "provider_roles": [
                "material_supplier",
                "service_provider",
                "supply_and_install_provider",
            ],
            "quantity": "20",
            "unit": "pcs",
            "unit_state": "known",
            "price": "1500",
            "currency": "PHP",
            "price_state": "known",
            "purchase_date": "2025-07-12",
            "date_state": "known",
            "has_evidence": True,
            "evidence_count": 1,
            "source_label": "Manual Source Entry",
        }
    ]


def test_reviewer_browses_linked_material_service_and_external_provider_memory(client):
    project = _create_project(client)
    _import_bundled_line(client, project)

    materials = client.get(f"/api/project-workspaces/{project['id']}/materials")
    services = client.get(f"/api/project-workspaces/{project['id']}/services")
    providers = client.get(f"/api/project-workspaces/{project['id']}/providers")

    assert materials.status_code == 200
    assert materials.json()["items"] == [
        {
            "memory_record_id": 1,
            "name": "PVC pipe",
            "category_path": "Plumbing / Pipes",
            "linked_purchase_line_count": 1,
            "source_submission_count": 1,
        }
    ]
    assert services.status_code == 200
    assert services.json()["items"] == [
        {
            "memory_record_id": 2,
            "name": "PVC pipe installation",
            "category_path": "Trade services / Pipe installation",
            "linked_purchase_line_count": 1,
            "source_submission_count": 1,
        }
    ]
    assert providers.status_code == 200
    assert providers.json()["items"] == [
        {
            "memory_record_id": 3,
            "name": "ABC Trading",
            "category_path": "Providers / General",
            "roles": [
                "material_supplier",
                "service_provider",
                "supply_and_install_provider",
            ],
            "linked_purchase_line_count": 1,
            "source_submission_count": 1,
        }
    ]


def test_legacy_internal_sentinel_does_not_match_arbitrary_named_provider(client):
    project = _create_project(client, contractor_assigned="Internal")
    _import_reviewed_line(
        client,
        project,
        {
            "linked_concepts": [
                {
                    "concept_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                }
            ],
            "provider_name": "ABC Trading",
        },
    )

    purchase_lines = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines"
    ).json()["items"]
    providers = client.get(
        f"/api/project-workspaces/{project['id']}/providers"
    ).json()["items"]

    assert purchase_lines[0]["provider_state"] == "external"
    assert purchase_lines[0]["provider_category_path"] == "Providers / General"
    assert providers[0]["name"] == "ABC Trading"
    assert providers[0]["category_path"] == "Providers / General"
    detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_lines[0]['id']}"
    ).json()
    assert detail["provider"]["state"] == "external"
    assert detail["provider"]["record"]["name"] == "ABC Trading"


def test_internal_and_unknown_provider_states_never_create_provider_memory(client):
    project = _create_project(
        client,
        contractor_assigned="  Quinlan   Construction  ",
    )
    _import_reviewed_line(
        client,
        project,
        {
            "linked_concepts": [
                {
                    "concept_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                }
            ],
            "provider_name": "quinlan construction",
        },
    )
    _import_reviewed_line(
        client,
        project,
        {
            "linked_concepts": [
                {
                    "concept_type": "service",
                    "name": "Hauling",
                    "top_level_category": "Trade services",
                    "subcategory": "Hauling",
                }
            ],
            "provider_state": "unknown",
        },
    )

    purchase_lines = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines"
    ).json()["items"]
    providers = client.get(
        f"/api/project-workspaces/{project['id']}/providers"
    ).json()["items"]

    assert purchase_lines[0]["provider_state"] == "internal"
    assert purchase_lines[0]["provider_name"] == "Internal"
    assert purchase_lines[0]["provider_roles"] == ["material_supplier"]
    assert purchase_lines[1]["provider_state"] == "unknown"
    assert purchase_lines[1]["provider_name"] is None
    assert purchase_lines[1]["provider_roles"] == []
    assert providers == []
    internal_detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_lines[0]['id']}"
    ).json()
    unknown_detail = client.get(
        f"/api/project-workspaces/{project['id']}/purchase-lines/{purchase_lines[1]['id']}"
    ).json()
    assert internal_detail["provider"] == {
        "state": "internal",
        "record": None,
        "roles": ["material_supplier"],
    }
    assert unknown_detail["provider"] == {
        "state": "unknown",
        "record": None,
        "roles": [],
    }


def test_provider_role_filters_match_any_selected_observed_role(client):
    project = _create_project(client)
    _import_bundled_line(client, project)

    any_match = client.get(
        f"/api/project-workspaces/{project['id']}/providers",
        params=[("roles", "service_provider"), ("roles", "unobserved_role")],
    )
    no_match = client.get(
        f"/api/project-workspaces/{project['id']}/providers",
        params={"roles": "unobserved_role"},
    )

    assert [item["name"] for item in any_match.json()["items"]] == ["ABC Trading"]
    assert no_match.json()["items"] == []


def test_review_exposes_independent_taxonomy_gates_for_new_linked_memory(client):
    project = _create_project(client)
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={
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
        },
    )

    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{submission['review_batch']['id']}"
    )

    gates = review.json()["candidates"][0]["taxonomy_gates"]
    assert [
        (gate["subject_type"], gate["subject_name"], gate["suggested_category_path"])
        for gate in gates
    ] == [
        ("material", "PVC pipe", "Plumbing / Pipes"),
        ("service", "PVC pipe installation", "Trade services / Pipe installation"),
        ("provider", "ABC Trading", "Providers / General"),
    ]
    assert all(gate["status"] == "needs_decision" for gate in gates)

    decision = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{submission['review_batch']['id']}/candidates/{submission['candidates'][0]['id']}/decision",
        json={
            "decision": "approved",
            "reviewed_payload": {
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
            },
        },
    )
    assert decision.status_code == 200

    blocked_review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{submission['review_batch']['id']}"
    ).json()
    blocked_import = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{submission['review_batch']['id']}/import"
    )

    assert blocked_review["review_batch"]["status"] == "review_in_progress"
    assert len(blocked_review["candidates"][0]["taxonomy_gates"]) == 3
    assert blocked_import.status_code == 400
    assert blocked_import.json()["detail"] == "Approved candidates require an accepted taxonomy gate"

    for index, gate in enumerate(gates):
        resolved = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{submission['review_batch']['id']}/taxonomy-gates/{gate['id']}/accept",
        )
        assert resolved.status_code == 200
        expected_status = "ready_to_import" if index == len(gates) - 1 else "review_in_progress"
        assert resolved.json()["review_batch"]["status"] == expected_status

    imported = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{submission['review_batch']['id']}/import"
    )
    assert imported.status_code == 200


def test_exact_name_reuse_preserves_categories_and_distinct_source_counts(client):
    project = _create_project(client)
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={"line_type": "material", "name": "PVC pipe"},
    )
    review_batch_id = submission["review_batch"]["id"]
    source_submission_id = submission["source_submission"]["id"]
    second_candidate_id = _add_candidate(
        client,
        project_workspace_id=project["id"],
        review_batch_id=review_batch_id,
        source_submission_id=source_submission_id,
        proposed_payload={"line_type": "material", "name": "pvc PIPE"},
    )
    reviewed_payloads = [
        (
            submission["candidates"][0]["id"],
            {
                "linked_concepts": [
                    {
                        "concept_type": "material",
                        "name": "PVC pipe",
                        "top_level_category": "Plumbing",
                        "subcategory": "Pipes",
                    }
                ],
                "provider_state": "external",
                "provider_name": "ABC Trading",
                "provider_top_level_category": "Providers",
                "provider_subcategory": "Suppliers",
            },
        ),
        (
            second_candidate_id,
            {
                "linked_concepts": [
                    {
                        "concept_type": "material",
                        "name": " pvc   PIPE ",
                        "top_level_category": "Electrical",
                        "subcategory": "Conduit",
                    }
                ],
                "provider_state": "external",
                "provider_name": " abc trading ",
                "provider_top_level_category": "Vendors",
                "provider_subcategory": "Other",
            },
        ),
    ]
    for candidate_id, reviewed_payload in reviewed_payloads:
        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}/"
            f"candidates/{candidate_id}/decision",
            json={"decision": "approved", "reviewed_payload": reviewed_payload},
        )
        assert response.status_code == 200

    accept_all_taxonomy_gates(
        client,
        project_workspace_id=project["id"],
        review_batch_id=review_batch_id,
    )

    imported = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}/import"
    )
    materials = client.get(
        f"/api/project-workspaces/{project['id']}/materials"
    ).json()["items"]
    providers = client.get(
        f"/api/project-workspaces/{project['id']}/providers"
    ).json()["items"]

    assert imported.status_code == 200
    assert len(imported.json()["imported_purchase_lines"]) == 2
    assert materials == [
        {
            "memory_record_id": materials[0]["memory_record_id"],
            "name": "PVC pipe",
            "category_path": "Plumbing / Pipes",
            "linked_purchase_line_count": 2,
            "source_submission_count": 1,
        }
    ]
    assert providers == [
        {
            "memory_record_id": providers[0]["memory_record_id"],
            "name": "ABC Trading",
            "category_path": "Providers / Suppliers",
            "roles": ["material_supplier"],
            "linked_purchase_line_count": 2,
            "source_submission_count": 1,
        }
    ]


def test_review_surfaces_project_scoped_existing_memory_matches(client):
    project = _create_project(client)
    _import_bundled_line(client, project)
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={"line_type": "material", "name": " pvc   PIPE "},
    )
    candidate_id = submission["candidates"][0]["id"]
    review_batch_id = submission["review_batch"]["id"]
    with client.app.state.session_factory() as session:
        from backend.app.review.models import ExtractedCandidate

        candidate = session.get(ExtractedCandidate, candidate_id)
        candidate.proposed_payload = {
            "linked_concepts": [
                {
                    "concept_type": "material",
                    "name": " pvc   PIPE ",
                    "category_suggestion": {
                        "top_level_category": "Electrical",
                        "subcategory": "Conduit",
                    },
                }
            ],
            "provider_state": "external",
            "provider_name": " abc trading ",
            "provider_category_suggestion": {
                "top_level_category": "Vendors",
                "subcategory": "Other",
            },
        }
        session.commit()

    candidate = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}"
    ).json()["candidates"][0]

    assert candidate["existing_memory_matches"] == [
        {
            "subject_type": "material",
            "subject_name": "PVC pipe",
            "category_path": "Plumbing / Pipes",
        },
        {
            "subject_type": "provider",
            "subject_name": "ABC Trading",
            "category_path": "Providers / General",
        },
    ]
    assert [gate["subject_type"] for gate in candidate["taxonomy_gates"]] == [
        "material",
        "provider",
    ]
    assert all(gate["status"] == "needs_decision" for gate in candidate["taxonomy_gates"])
