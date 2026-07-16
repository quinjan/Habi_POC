from backend.tests.db import make_postgres_test_client
from backend.tests.test_taxonomy_decisions_api import (
    add_manual_submission_to_project,
    add_candidate_to_batch,
    create_manual_submission,
    create_taxonomy_path,
    set_candidate_category_suggestion,
)


def test_existing_taxonomy_path_requires_candidate_gate_acceptance(tmp_path):
    with make_postgres_test_client() as client:
        project, submission = create_manual_submission(
            client, "Arnaiz Residence Renovation"
        )
        candidate_id = submission["candidates"][0]["id"]
        review_batch_id = submission["review_batch"]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )

        approved = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/candidates/{candidate_id}/decision",
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
                    "provider_state": "unknown",
                },
            },
        )

        gate = approved.json()["taxonomy_gates"][0]
        blocked_import = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/import"
        )
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate['id']}/accept"
        )
        duplicate_acceptance = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate['id']}/accept"
        )

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved_for_import"
    assert gate["subject_type"] == "material"
    assert gate["subject_name"] == "PVC pipe"
    assert gate["original_ai_category_path"] == "Plumbing / Pipes"
    assert gate["reviewer_draft_category_path"] is None
    assert gate["selected_proposal"] == "ai_suggestion"
    assert gate["selected_category_path"] == "Plumbing / Pipes"
    assert gate["status"] == "needs_decision"
    assert blocked_import.status_code == 400
    assert (
        blocked_import.json()["detail"]
        == "Approved candidates require an accepted taxonomy gate"
    )
    assert accepted.status_code == 200
    accepted_gate = accepted.json()["candidates"][0]["taxonomy_gates"][0]
    assert accepted_gate["status"] == "accepted"
    assert accepted_gate["accepted_category_path"] == "Plumbing / Pipes"
    assert accepted_gate["accepted_source"] == "ai_suggestion"
    assert accepted.json()["review_batch"]["status"] == "ready_to_import"
    assert duplicate_acceptance.status_code == 409
    assert duplicate_acceptance.json()["detail"] == "Taxonomy gate is already accepted"


def test_reviewer_draft_has_no_taxonomy_side_effect_until_acceptance(tmp_path):
    with make_postgres_test_client() as client:
        project, submission = create_manual_submission(
            client, "Arnaiz Residence Renovation"
        )
        candidate_id = submission["candidates"][0]["id"]
        review_batch_id = submission["review_batch"]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        approved = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/candidates/{candidate_id}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Mechanical",
                    "subcategory": "Pipe Materials",
                    "provider_state": "unknown",
                },
            },
        )
        gate_id = approved.json()["taxonomy_gates"][0]["id"]

        draft = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/reviewer-draft",
            json={
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
                "apply_to_similar": False,
            },
        )
        nodes_before_acceptance = client.get(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes"
        )
        later_submission = add_manual_submission_to_project(client, project["id"])
        set_candidate_category_suggestion(
            client,
            later_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        later_batch_before_acceptance = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{later_submission['review_batch']['id']}"
        )

        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/accept"
        )
        nodes_after_acceptance = client.get(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes"
        )

    assert draft.status_code == 200
    assert draft.json()["affected_count"] == 0
    draft_gate = draft.json()["review_batch"]["candidates"][0]["taxonomy_gates"][0]
    assert draft_gate["status"] == "needs_decision"
    assert draft_gate["original_ai_category_path"] == "Mechanical / Pipe Materials"
    assert draft_gate["reviewer_draft_category_path"] == "Plumbing / Pipes"
    assert draft_gate["selected_proposal"] == "reviewer_draft"
    assert draft_gate["decision_history"] == []
    assert nodes_before_acceptance.json()["items"] == []
    assert (
        later_batch_before_acceptance.json()["candidates"][0]["taxonomy_default"]
        is None
    )
    accepted_gate = accepted.json()["candidates"][0]["taxonomy_gates"][0]
    assert accepted_gate["accepted_category_path"] == "Plumbing / Pipes"
    assert accepted_gate["accepted_source"] == "reviewer_draft"
    assert accepted_gate["decision_history"][0]["accepted_source"] == "reviewer_draft"
    assert [item["path"] for item in nodes_after_acceptance.json()["items"]] == [
        "Plumbing",
        "Plumbing / Pipes",
    ]


def test_reviewer_draft_propagates_only_to_matching_pending_subject_gates(tmp_path):
    with make_postgres_test_client() as client:
        project, submission = create_manual_submission(
            client, "Arnaiz Residence Renovation"
        )
        target_candidate_id = submission["candidates"][0]["id"]
        review_batch_id = submission["review_batch"]["id"]
        source_submission_id = submission["source_submission"]["id"]
        set_candidate_category_suggestion(
            client,
            target_candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        matching_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=review_batch_id,
            source_submission_id=source_submission_id,
            proposed_payload={
                "line_type": "material",
                "name": "PVC elbow",
                "category_suggestion": {
                    "top_level_category": " mechanical ",
                    "subcategory": "PIPE   MATERIALS",
                },
            },
        )
        service_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=review_batch_id,
            source_submission_id=source_submission_id,
            proposed_payload={
                "line_type": "service",
                "name": "Pipe installation",
                "category_suggestion": {
                    "top_level_category": "Mechanical",
                    "subcategory": "Pipe Materials",
                },
            },
        )
        accepted_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=review_batch_id,
            source_submission_id=source_submission_id,
            proposed_payload={
                "line_type": "material",
                "name": "PVC tee",
                "category_suggestion": {
                    "top_level_category": "Mechanical",
                    "subcategory": "Pipe Materials",
                },
            },
        )
        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}"
        ).json()
        gates_by_candidate = {
            candidate["id"]: candidate["taxonomy_gates"][0]
            for candidate in batch["candidates"]
        }
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/"
            f"{gates_by_candidate[accepted_candidate_id]['id']}/accept"
        )

        propagated = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/"
            f"{gates_by_candidate[target_candidate_id]['id']}/reviewer-draft",
            json={
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
                "apply_to_similar": True,
            },
        )

    assert propagated.status_code == 200
    assert propagated.json()["affected_count"] == 1
    result_gates = {
        candidate["id"]: candidate["taxonomy_gates"][0]
        for candidate in propagated.json()["review_batch"]["candidates"]
    }
    assert result_gates[target_candidate_id]["reviewer_draft_category_path"] == "Plumbing / Pipes"
    assert result_gates[matching_candidate_id]["reviewer_draft_category_path"] == "Plumbing / Pipes"
    assert result_gates[matching_candidate_id]["selected_proposal"] == "reviewer_draft"
    assert result_gates[matching_candidate_id]["status"] == "needs_decision"
    assert result_gates[service_candidate_id]["reviewer_draft_category_path"] is None
    assert result_gates[accepted_candidate_id]["status"] == "accepted"
    assert result_gates[accepted_candidate_id]["reviewer_draft_category_path"] is None


def test_reviewer_can_select_ai_suggestion_after_saving_a_draft(tmp_path):
    with make_postgres_test_client() as client:
        project, submission = create_manual_submission(
            client, "Arnaiz Residence Renovation"
        )
        candidate_id = submission["candidates"][0]["id"]
        review_batch_id = submission["review_batch"]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{review_batch_id}"
        ).json()
        gate_id = batch["candidates"][0]["taxonomy_gates"][0]["id"]
        client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/reviewer-draft",
            json={
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
            },
        )

        selected = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/selection",
            json={"selected_proposal": "ai_suggestion"},
        )
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/accept"
        )

    assert selected.status_code == 200
    selected_gate = selected.json()["candidates"][0]["taxonomy_gates"][0]
    assert selected_gate["reviewer_draft_category_path"] == "Plumbing / Pipes"
    assert selected_gate["selected_proposal"] == "ai_suggestion"
    assert selected_gate["selected_category_path"] == "Mechanical / Pipe Materials"
    accepted_gate = accepted.json()["candidates"][0]["taxonomy_gates"][0]
    assert accepted_gate["accepted_source"] == "ai_suggestion"
    assert accepted_gate["accepted_category_path"] == "Mechanical / Pipe Materials"


def test_editing_accepted_gate_restores_import_block_and_retains_history(tmp_path):
    with make_postgres_test_client() as client:
        project, submission = create_manual_submission(
            client, "Arnaiz Residence Renovation"
        )
        candidate_id = submission["candidates"][0]["id"]
        review_batch_id = submission["review_batch"]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        approved = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/candidates/{candidate_id}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Mechanical",
                    "subcategory": "Pipe Materials",
                    "provider_state": "unknown",
                },
            },
        ).json()
        gate_id = approved["taxonomy_gates"][0]["id"]
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/accept"
        )

        edited = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/edit"
        )
        blocked_import = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/import"
        )
        client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/reviewer-draft",
            json={
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
            },
        )
        reaccepted = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/accept"
        )
        imported = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/import"
        )
        materials = client.get(
            f"/api/project-workspaces/{project['id']}/materials"
        )
        terminal_edit = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/taxonomy-gates/{gate_id}/edit"
        )

    assert accepted.json()["review_batch"]["status"] == "ready_to_import"
    assert edited.status_code == 200
    edited_gate = edited.json()["candidates"][0]["taxonomy_gates"][0]
    assert edited_gate["status"] == "needs_decision"
    assert edited_gate["accepted_category_path"] is None
    assert edited_gate["decision_history"][0]["superseded"] is True
    assert edited.json()["review_batch"]["status"] == "review_in_progress"
    assert blocked_import.status_code == 400
    reaccepted_gate = reaccepted.json()["candidates"][0]["taxonomy_gates"][0]
    assert len(reaccepted_gate["decision_history"]) == 2
    assert reaccepted_gate["decision_history"][0]["superseded"] is True
    assert reaccepted_gate["decision_history"][1]["superseded"] is False
    assert reaccepted_gate["accepted_source"] == "reviewer_draft"
    assert reaccepted_gate["accepted_category_path"] == "Plumbing / Pipes"
    assert imported.status_code == 200
    assert materials.json()["items"][0]["category_path"] == "Plumbing / Pipes"
    assert terminal_edit.status_code == 409
    assert terminal_edit.json()["detail"] == "Terminal review batches cannot be changed"


def test_internal_provider_has_no_active_provider_taxonomy_gate(tmp_path):
    with make_postgres_test_client() as client:
        project, submission = create_manual_submission(
            client, "Arnaiz Residence Renovation"
        )
        candidate_id = submission["candidates"][0]["id"]
        review_batch_id = submission["review_batch"]["id"]
        with client.app.state.session_factory() as session:
            from backend.app.review.models import ExtractedCandidate

            candidate = session.get(ExtractedCandidate, candidate_id)
            candidate.proposed_payload = {
                "linked_concepts": [
                    {
                        "concept_type": "service",
                        "name": "Pipe installation",
                        "category_suggestion": {
                            "top_level_category": "Trade services",
                            "subcategory": "Pipe installation",
                        },
                    }
                ],
                "provider_state": "external",
                "provider_name": "ABC Trading",
                "provider_category_suggestion": {
                    "top_level_category": "Providers",
                    "subcategory": "General",
                },
            }
            session.commit()

        approved = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/"
            f"{review_batch_id}/candidates/{candidate_id}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "linked_concepts": [
                        {
                            "concept_type": "service",
                            "name": "Pipe installation",
                            "top_level_category": "Trade services",
                            "subcategory": "Pipe installation",
                        }
                    ],
                    "provider_state": "internal",
                },
            },
        )

    assert approved.status_code == 200
    assert [
        gate["subject_type"] for gate in approved.json()["taxonomy_gates"]
    ] == ["service"]
