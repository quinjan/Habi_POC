from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.tests.db import make_postgres_test_client
from backend.tests.manual_submission_helpers import create_review_ready_manual_submission


def make_client(_tmp_path):
    return make_postgres_test_client()


def test_taxonomy_decision_is_project_scoped_and_rejects_cross_project_mapping(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        other_project = client.post(
            "/api/project-workspaces",
            json={
                "project_name": "Ortigas Office Fit-Out",
                "project_type": "Commercial fit-out",
                "location": "Pasig City",
                "completion_year": 2024,
            },
        ).json()
        other_project_node_id = create_taxonomy_path(
            client,
            project_workspace_id=other_project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        local_node_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        cross_project_mapping = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "mapped",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
                "resolved_taxonomy_node_id": other_project_node_id,
            },
        )
        local_mapping = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "mapped",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
                "resolved_taxonomy_node_id": local_node_id,
            },
        )

    assert cross_project_mapping.status_code == 400
    assert (
        cross_project_mapping.json()["detail"]
        == "Mapped taxonomy node must belong to the selected Project Workspace"
    )
    assert local_mapping.status_code == 201
    decision = local_mapping.json()["taxonomy_decisions"][0]
    assert decision["project_workspace_id"] == project["id"]
    assert decision["review_batch_id"] == submission["review_batch"]["id"]
    assert decision["decision"] == "mapped"
    assert decision["resolved_taxonomy_node_id"] == local_node_id


def test_taxonomy_decision_rejects_suggestion_not_present_in_review_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        local_node_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "mapped",
                "suggested_top_level_category": "Electrical",
                "suggested_subcategory": "Lighting",
                "resolved_taxonomy_node_id": local_node_id,
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Taxonomy decision suggestion must appear in the Review Batch"


def test_mapped_taxonomy_decision_rejects_top_level_target(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        top_level_node_id = create_taxonomy_top_level(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
        )
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "mapped",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
                "resolved_taxonomy_node_id": top_level_node_id,
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Mapped taxonomy decisions require a subcategory leaf node"


def test_rejected_taxonomy_decision_keeps_candidate_and_gate_unresolved_with_prior_context(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        candidate_id = submission["candidates"][0]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "rejected",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )

    assert response.status_code == 201
    candidate = response.json()["candidates"][0]
    decision = response.json()["taxonomy_decisions"][0]
    assert candidate["decision"] is None
    assert candidate["taxonomy_gate"] == {
        "status": "new_taxonomy_path",
        "reason": "new_taxonomy_path",
        "suggested_category_path": "Mechanical / Pipe Materials",
        "resolved_category_path": None,
        "decision": None,
        "taxonomy_decision_id": None,
        "prior_rejection": {
            "taxonomy_decision_id": decision["id"],
            "suggested_category_path": "Mechanical / Pipe Materials",
        },
    }


def test_rejected_taxonomy_decision_does_not_retain_resolved_node(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        local_node_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "rejected",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
                "resolved_taxonomy_node_id": local_node_id,
            },
        )

    assert response.status_code == 201
    decision = response.json()["taxonomy_decisions"][0]
    assert decision["decision"] == "rejected"
    assert decision["resolved_taxonomy_node_id"] is None


def test_approved_taxonomy_decision_defaults_later_matching_suggestion_without_mutating_payload(tmp_path):
    with make_client(tmp_path) as client:
        project, first_submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        set_candidate_category_suggestion(
            client,
            first_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        decision_response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{first_submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "approved",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )

        second_submission = add_manual_submission_to_project(client, project["id"])
        set_candidate_category_suggestion(
            client,
            second_submission["candidates"][0]["id"],
            top_level_category=" mechanical ",
            subcategory="PIPE   MATERIALS",
        )
        later_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{second_submission['review_batch']['id']}"
        )

    decision = decision_response.json()["taxonomy_decisions"][0]
    candidate = later_batch.json()["candidates"][0]
    assert candidate["reviewed_payload"] is None
    assert candidate["taxonomy_default"] == {
        "resolved_category_path": "Mechanical / Pipe Materials",
        "source": "approved_taxonomy_decision",
        "provenance_text": "Defaulted from a previous approved taxonomy decision: Mechanical / Pipe Materials",
        "taxonomy_decision_id": decision["id"],
    }


def test_mapped_taxonomy_decision_defaults_later_matching_suggestion(tmp_path):
    with make_client(tmp_path) as client:
        project, first_submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        mapped_leaf_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        set_candidate_category_suggestion(
            client,
            first_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        decision_response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{first_submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "mapped",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
                "resolved_taxonomy_node_id": mapped_leaf_id,
            },
        )

        second_submission = add_manual_submission_to_project(client, project["id"])
        set_candidate_category_suggestion(
            client,
            second_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        later_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{second_submission['review_batch']['id']}"
        )

    decision = decision_response.json()["taxonomy_decisions"][0]
    assert later_batch.json()["candidates"][0]["taxonomy_default"] == {
        "resolved_category_path": "Plumbing / Pipes",
        "source": "mapped_taxonomy_decision",
        "provenance_text": "Defaulted from a previous mapping: Mechanical / Pipe Materials -> Plumbing / Pipes",
        "taxonomy_decision_id": decision["id"],
    }


def test_taxonomy_defaults_do_not_cross_project_workspaces(tmp_path):
    with make_client(tmp_path) as client:
        project, first_submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        set_candidate_category_suggestion(
            client,
            first_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{first_submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "approved",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )
        other_project, other_submission = create_manual_submission(client, "Ortigas Office Fit-Out")
        set_candidate_category_suggestion(
            client,
            other_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        other_batch = client.get(
            f"/api/project-workspaces/{other_project['id']}/review-batches/{other_submission['review_batch']['id']}"
        )

    assert other_batch.status_code == 200
    assert other_batch.json()["candidates"][0]["taxonomy_default"] is None
    assert other_batch.json()["candidates"][0]["taxonomy_gate"]["status"] == "new_taxonomy_path"


def test_latest_taxonomy_decision_wins_for_defaults_and_gate_context(tmp_path):
    with make_client(tmp_path) as client:
        project, first_submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        set_candidate_category_suggestion(
            client,
            first_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{first_submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "approved",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )
        latest_response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{first_submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "rejected",
                "suggested_top_level_category": " mechanical ",
                "suggested_subcategory": "PIPE   MATERIALS",
            },
        )
        second_submission = add_manual_submission_to_project(client, project["id"])
        set_candidate_category_suggestion(
            client,
            second_submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        later_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{second_submission['review_batch']['id']}"
        )

    latest_decision = latest_response.json()["taxonomy_decisions"][-1]
    candidate = later_batch.json()["candidates"][0]
    assert candidate["taxonomy_default"] is None
    assert candidate["taxonomy_gate"]["status"] == "new_taxonomy_path"
    assert candidate["taxonomy_gate"]["prior_rejection"]["taxonomy_decision_id"] == latest_decision["id"]


def test_one_taxonomy_decision_resolves_repeated_matching_suggestions_in_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "material",
                "name": "PVC pipe fittings",
                "category_suggestion": {
                    "top_level_category": " mechanical ",
                    "subcategory": "PIPE   MATERIALS",
                },
            },
        )
        set_candidate_category_suggestion(
            client,
            first_candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "approved",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )

    assert response.status_code == 201
    gates_by_candidate = {
        candidate["id"]: candidate["taxonomy_gate"]
        for candidate in response.json()["candidates"]
    }
    assert gates_by_candidate[first_candidate_id]["status"] == "resolved_by_approval"
    assert gates_by_candidate[second_candidate_id]["status"] == "resolved_by_approval"


def test_taxonomy_leaf_listing_is_project_scoped_and_returns_two_level_paths(tmp_path):
    with make_client(tmp_path) as client:
        project, _submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        other_project = client.post(
            "/api/project-workspaces",
            json={
                "project_name": "Ortigas Office Fit-Out",
                "project_type": "Commercial fit-out",
                "location": "Pasig City",
                "completion_year": 2024,
            },
        ).json()
        local_leaf_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        create_taxonomy_top_level(
            client,
            project_workspace_id=project["id"],
            top_level_category="Mechanical",
        )
        create_taxonomy_path(
            client,
            project_workspace_id=other_project["id"],
            top_level_category="Electrical",
            subcategory="Lighting",
        )

        response = client.get(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes?leaf_only=true"
        )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": local_leaf_id,
            "name": "Pipes",
            "parent_id": 1,
            "path": "Plumbing / Pipes",
        }
    ]


def test_rename_taxonomy_node_returns_updated_path_and_updates_live_purchase_line_display(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        candidate_id = submission["candidates"][0]["id"]
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{candidate_id}/decision",
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
                },
            },
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )
        leaf_id = client.get(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes?leaf_only=true"
        ).json()["items"][0]["id"]

        rename_response = client.patch(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes/{leaf_id}",
            json={"name": "Pipe Materials"},
        )
        purchase_lines = client.get(f"/api/project-workspaces/{project['id']}/purchase-lines")

    assert rename_response.status_code == 200
    assert rename_response.json() == {
        "id": leaf_id,
        "name": "Pipe Materials",
        "parent_id": 1,
        "path": "Plumbing / Pipe Materials",
    }
    assert purchase_lines.json()["items"][0]["category_path"] == "Plumbing / Pipe Materials"


def test_rename_taxonomy_node_rejects_duplicate_sibling_name_after_normalization(tmp_path):
    with make_client(tmp_path) as client:
        project, _submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        fittings_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Fittings",
        )

        response = client.patch(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes/{fittings_id}",
            json={"name": "  PIPES  "},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Taxonomy node names must be unique among siblings"


def test_rename_taxonomy_node_rejects_blank_name_after_trimming(tmp_path):
    with make_client(tmp_path) as client:
        project, _submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        leaf_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )

        response = client.patch(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes/{leaf_id}",
            json={"name": "   "},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Taxonomy node name cannot be blank"


def test_database_rejects_duplicate_root_taxonomy_names_after_normalization(tmp_path):
    with make_client(tmp_path) as client:
        project, _submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        create_taxonomy_top_level(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
        )

        with client.app.state.session_factory() as session:
            from backend.app.taxonomy.models import TaxonomyNode

            session.add(
                TaxonomyNode(
                    project_workspace_id=project["id"],
                    parent_id=None,
                    name="  PLUMBING  ",
                )
            )
            try:
                session.commit()
                duplicate_rejected = False
            except IntegrityError:
                duplicate_rejected = True

    assert duplicate_rejected is True


def test_rename_taxonomy_node_rejects_reparenting_attempts(tmp_path):
    with make_client(tmp_path) as client:
        project, _submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        leaf_id = create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Plumbing",
            subcategory="Pipes",
        )
        other_parent_id = create_taxonomy_top_level(
            client,
            project_workspace_id=project["id"],
            top_level_category="Mechanical",
        )

        response = client.patch(
            f"/api/project-workspaces/{project['id']}/taxonomy-nodes/{leaf_id}",
            json={"name": "Pipes", "parent_id": other_parent_id},
        )

    assert response.status_code == 422


def test_terminal_review_batch_rejects_taxonomy_decisions(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        candidate_id = submission["candidates"][0]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{candidate_id}/decision",
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
                },
            },
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "rejected",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Terminal review batches cannot be changed"


def test_taxonomy_decision_returns_updated_review_batch_detail(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        candidate_id = submission["candidates"][0]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "approved",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["review_batch"]["id"] == submission["review_batch"]["id"]
    assert body["candidates"][0]["id"] == candidate_id
    assert body["candidates"][0]["taxonomy_gate"]["status"] == "resolved_by_approval"
    assert body["candidates"][0]["taxonomy_gate"]["resolved_category_path"] == "Mechanical / Pipe Materials"
    assert body["taxonomy_decisions"][0]["decision"] == "approved"


def test_candidate_decision_response_includes_taxonomy_context(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        candidate_id = submission["candidates"][0]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{candidate_id}/decision",
            json={
                "decision": "rejected",
                "reviewed_payload": None,
            },
        )

    assert response.status_code == 200
    assert response.json()["taxonomy_gate"] == {
        "status": "new_taxonomy_path",
        "reason": "new_taxonomy_path",
        "suggested_category_path": "Mechanical / Pipe Materials",
        "resolved_category_path": None,
        "decision": None,
        "taxonomy_decision_id": None,
        "prior_rejection": None,
    }


def test_taxonomy_decision_rejects_deferred_state(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "deferred",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )

    assert response.status_code == 422


def test_new_subcategory_under_existing_top_level_requires_taxonomy_gate(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Mechanical",
            subcategory="Equipment",
        )
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert batch.status_code == 200
    assert batch.json()["candidates"][0]["taxonomy_gate"] == {
        "status": "new_taxonomy_path",
        "reason": "new_taxonomy_path",
        "suggested_category_path": "Mechanical / Pipe Materials",
        "resolved_category_path": None,
        "decision": None,
        "taxonomy_decision_id": None,
        "prior_rejection": None,
    }


def test_top_level_only_suggestion_shows_subcategory_required_gate(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Mechanical",
            subcategory="Equipment",
        )
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="Mechanical",
            subcategory="",
        )

        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert batch.status_code == 200
    assert batch.json()["candidates"][0]["taxonomy_gate"] == {
        "status": "subcategory_required",
        "reason": "subcategory_required",
        "suggested_category_path": "Mechanical",
        "resolved_category_path": None,
        "decision": None,
        "taxonomy_decision_id": None,
        "prior_rejection": None,
    }


def test_existing_two_level_taxonomy_path_suggestion_has_no_gate(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        create_taxonomy_path(
            client,
            project_workspace_id=project["id"],
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )
        set_candidate_category_suggestion(
            client,
            submission["candidates"][0]["id"],
            top_level_category="  mechanical ",
            subcategory="PIPE   MATERIALS",
        )

        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert batch.status_code == 200
    assert batch.json()["candidates"][0]["taxonomy_gate"] is None


def test_new_top_level_taxonomy_gate_stays_unready_until_category_path_is_reviewed(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        candidate_id = submission["candidates"][0]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{candidate_id}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "quantity": "20",
                    "unit": "pcs",
                    "price": "1500",
                    "provider_name": "ABC Trading",
                },
            },
        )
        unresolved_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )
        blocked_import = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

        taxonomy_decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-decisions",
            json={
                "decision": "approved",
                "suggested_top_level_category": "Mechanical",
                "suggested_subcategory": "Pipe Materials",
            },
        )
        reviewed_category = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{candidate_id}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Mechanical",
                    "subcategory": "Pipe Materials",
                    "quantity": "20",
                    "unit": "pcs",
                    "price": "1500",
                    "provider_name": "ABC Trading",
                },
            },
        )
        ready_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert decision.status_code == 200
    assert unresolved_batch.json()["review_batch"]["status"] == "review_in_progress"
    assert unresolved_batch.json()["candidates"][0]["taxonomy_gate"] == {
        "status": "new_taxonomy_path",
        "reason": "new_taxonomy_path",
        "suggested_category_path": "Mechanical / Pipe Materials",
        "resolved_category_path": None,
        "decision": None,
        "taxonomy_decision_id": None,
        "prior_rejection": None,
    }
    assert blocked_import.status_code == 400
    assert blocked_import.json()["detail"] == "Approved candidates require a resolved category path"
    assert taxonomy_decision.status_code == 201
    assert taxonomy_decision.json()["taxonomy_decisions"][0]["decision"] == "approved"
    assert taxonomy_decision.json()["taxonomy_decisions"][0]["resolved_taxonomy_node_id"] is not None
    assert reviewed_category.status_code == 200
    assert ready_batch.json()["review_batch"]["status"] == "ready_to_import"
    assert ready_batch.json()["candidates"][0]["taxonomy_gate"] is None


def test_reviewer_supplied_category_path_imports_without_taxonomy_decision(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        candidate_id = submission["candidates"][0]["id"]
        set_candidate_category_suggestion(
            client,
            candidate_id,
            top_level_category="Mechanical",
            subcategory="Pipe Materials",
        )

        decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{candidate_id}/decision",
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
    assert purchase_lines.json()["items"][0]["category_path"] == "Plumbing / Pipes"


def test_ready_to_import_requires_every_approved_candidate_to_satisfy_import_gates(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client, "Arnaiz Residence Renovation")
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "material",
                "name": "PVC pipe fittings",
                "quantity": "10",
                "unit": "pcs",
                "price": "450",
                "provider_name": "ABC Trading",
            },
        )

        first_decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{first_candidate_id}/decision",
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
                },
            },
        )
        second_decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{second_candidate_id}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe fittings",
                    "top_level_category": "Plumbing",
                    "quantity": "10",
                    "unit": "pcs",
                    "price": "450",
                    "provider_name": "ABC Trading",
                },
            },
        )
        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )
        imported = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert first_decision.status_code == 200
    assert second_decision.status_code == 200
    assert batch.json()["review_batch"]["status"] == "review_in_progress"
    assert imported.status_code == 400
    assert imported.json()["detail"] == "Approved candidates require a resolved category path"


def create_manual_submission(client: TestClient, project_name: str):
    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": project_name,
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
        },
    )
    return project, submission


def add_manual_submission_to_project(client: TestClient, project_workspace_id: int):
    return create_review_ready_manual_submission(
        client,
        project_workspace_id=project_workspace_id,
        structured_payload={
            "line_type": "material",
            "name": "PVC pipe fittings",
            "quantity": "10",
            "unit": "pcs",
            "price": "450",
            "provider_name": "ABC Trading",
        },
    )


def create_taxonomy_path(
    client: TestClient,
    *,
    project_workspace_id: int,
    top_level_category: str,
    subcategory: str,
) -> int:
    from sqlalchemy import select

    from backend.app.taxonomy.models import TaxonomyNode

    with client.app.state.session_factory() as session:
        top_level = session.scalar(
            select(TaxonomyNode).where(
                TaxonomyNode.project_workspace_id == project_workspace_id,
                TaxonomyNode.parent_id.is_(None),
                TaxonomyNode.normalized_name == " ".join(top_level_category.casefold().split()),
            )
        )
        if top_level is None:
            top_level = TaxonomyNode(
                project_workspace_id=project_workspace_id,
                parent_id=None,
                name=top_level_category,
            )
            session.add(top_level)
            session.flush()
        child = TaxonomyNode(
            project_workspace_id=project_workspace_id,
            parent_id=top_level.id,
            name=subcategory,
        )
        session.add(child)
        session.commit()
        return child.id


def create_taxonomy_top_level(
    client: TestClient,
    *,
    project_workspace_id: int,
    top_level_category: str,
) -> int:
    from backend.app.taxonomy.models import TaxonomyNode

    with client.app.state.session_factory() as session:
        top_level = TaxonomyNode(
            project_workspace_id=project_workspace_id,
            parent_id=None,
            name=top_level_category,
        )
        session.add(top_level)
        session.commit()
        return top_level.id


def set_candidate_category_suggestion(
    client: TestClient,
    candidate_id: int,
    *,
    top_level_category: str,
    subcategory: str,
) -> None:
    from backend.app.review.models import ExtractedCandidate

    with client.app.state.session_factory() as session:
        candidate = session.get(ExtractedCandidate, candidate_id)
        candidate.proposed_payload = {
            **candidate.proposed_payload,
            "category_suggestion": {
                "top_level_category": top_level_category,
                "subcategory": subcategory,
            },
        }
        session.commit()


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
