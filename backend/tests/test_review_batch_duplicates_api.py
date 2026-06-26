from fastapi.testclient import TestClient

from backend.tests.db import make_postgres_test_client


def make_client(_tmp_path):
    return make_postgres_test_client()


def test_duplicate_group_membership_merge_and_unmerge_workflow(tmp_path):
    with make_client(tmp_path) as client:
        project = create_project(client)
        submission = create_manual_submission(client, project["id"])
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "material", "name": "PVC pipes"},
        )
        outside_group_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "service", "name": "Hauling"},
        )

        group = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/duplicate-groups",
            json={"member_candidate_ids": [first_candidate_id, second_candidate_id]},
        )
        bad_merge = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{first_candidate_id}/decision",
            json={
                "decision": "merged",
                "merged_into_candidate_id": outside_group_candidate_id,
            },
        )
        good_merge = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{first_candidate_id}/decision",
            json={
                "decision": "merged",
                "merged_into_candidate_id": second_candidate_id,
            },
        )
        added_member = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/duplicate-groups/{group.json()['id']}/members",
            json={"add_candidate_ids": [outside_group_candidate_id]},
        )
        removed_member = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/duplicate-groups/{group.json()['id']}/members",
            json={"remove_candidate_ids": [outside_group_candidate_id]},
        )
        unmerged = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{first_candidate_id}/decision",
            json={"decision": None, "merged_into_candidate_id": None},
        )

    assert group.status_code == 201
    assert group.json()["member_candidate_ids"] == [first_candidate_id, second_candidate_id]
    assert bad_merge.status_code == 400
    assert bad_merge.json()["detail"] == "Merged candidates must target a candidate in the same duplicate group"
    assert good_merge.status_code == 200
    assert good_merge.json()["decision"] == "merged"
    assert good_merge.json()["merged_into_candidate_id"] == second_candidate_id
    assert added_member.status_code == 200
    assert added_member.json()["member_candidate_ids"] == [
        first_candidate_id,
        second_candidate_id,
        outside_group_candidate_id,
    ]
    assert removed_member.status_code == 200
    assert removed_member.json()["member_candidate_ids"] == [first_candidate_id, second_candidate_id]
    assert unmerged.status_code == 200
    assert unmerged.json()["status"] == "pending_review"
    assert unmerged.json()["decision"] is None
    assert unmerged.json()["merged_into_candidate_id"] is None


def test_duplicate_group_with_multiple_approved_survivors_blocks_readiness_and_import(tmp_path):
    with make_client(tmp_path) as client:
        project = create_project(client)
        submission = create_manual_submission(client, project["id"])
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "material", "name": "PVC pipes"},
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/duplicate-groups",
            json={"member_candidate_ids": [first_candidate_id, second_candidate_id]},
        )

        approve_candidate(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            candidate_id=first_candidate_id,
            name="PVC pipe",
        )
        approve_candidate(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            candidate_id=second_candidate_id,
            name="PVC pipes",
        )
        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )
        imported = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

    assert batch.status_code == 200
    assert batch.json()["review_batch"]["status"] == "review_in_progress"
    assert batch.json()["duplicate_conflicts"] == ["multiple_approved_survivors"]
    assert imported.status_code == 400
    assert imported.json()["detail"] == "Duplicate conflicts must be resolved before import"


def test_duplicate_merge_conflicts_are_reported_for_self_merge_unresolved_target_and_loop(tmp_path):
    with make_client(tmp_path) as client:
        project = create_project(client)
        submission = create_manual_submission(client, project["id"])
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "material", "name": "PVC pipes"},
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/duplicate-groups",
            json={"member_candidate_ids": [first_candidate_id, second_candidate_id]},
        )

        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{first_candidate_id}/decision",
            json={"decision": "merged", "merged_into_candidate_id": first_candidate_id},
        )
        self_merge_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{first_candidate_id}/decision",
            json={"decision": "merged", "merged_into_candidate_id": second_candidate_id},
        )
        unresolved_target_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{second_candidate_id}/decision",
            json={"decision": "merged", "merged_into_candidate_id": first_candidate_id},
        )
        loop_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert self_merge_batch.json()["duplicate_conflicts"] == ["self_merge"]
    assert unresolved_target_batch.json()["duplicate_conflicts"] == ["unresolved_merge_target"]
    assert loop_batch.json()["duplicate_conflicts"] == ["merge_loop"]


def test_persisted_invalid_merge_targets_are_reported_as_duplicate_conflicts(tmp_path):
    with make_client(tmp_path) as client:
        project = create_project(client)
        submission = create_manual_submission(client, project["id"])
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "material", "name": "PVC pipes"},
        )
        outside_group_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "service", "name": "Hauling"},
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/duplicate-groups",
            json={"member_candidate_ids": [first_candidate_id, second_candidate_id]},
        )

        force_candidate_merge_state(
            client,
            first_candidate_id,
            merged_into_candidate_id=None,
        )
        missing_target_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )
        force_candidate_merge_state(
            client,
            first_candidate_id,
            merged_into_candidate_id=outside_group_candidate_id,
        )
        outside_target_batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        )

    assert missing_target_batch.json()["duplicate_conflicts"] == ["missing_merge_target"]
    assert outside_target_batch.json()["duplicate_conflicts"] == [
        "merge_target_outside_duplicate_group"
    ]


def test_imports_approved_survivor_once_and_promotes_merged_candidate_evidence(tmp_path):
    with make_client(tmp_path) as client:
        project = create_project(client)
        submission = create_manual_submission(client, project["id"])
        survivor_candidate_id = submission["candidates"][0]["id"]
        merged_source_submission_id = add_manual_source_entry(
            client,
            project_workspace_id=project["id"],
            structured_payload={
                "line_type": "material",
                "name": "PVC pipe duplicate receipt",
                "remarks_or_terms": "Second receipt evidence",
            },
        )
        merged_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=merged_source_submission_id,
            proposed_payload={
                "line_type": "material",
                "name": "PVC pipe duplicate receipt",
            },
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/duplicate-groups",
            json={"member_candidate_ids": [survivor_candidate_id, merged_candidate_id]},
        )
        approve_candidate(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            candidate_id=survivor_candidate_id,
            name="PVC pipe",
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{merged_candidate_id}/decision",
            json={
                "decision": "merged",
                "merged_into_candidate_id": survivor_candidate_id,
            },
        )

        imported = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )
        purchase_lines = client.get(
            f"/api/project-workspaces/{project['id']}/purchase-lines"
        )
        evidence_contents = imported_purchase_line_evidence_contents(
            client,
            imported.json()["imported_purchase_lines"][0]["id"],
        )

    assert imported.status_code == 200
    assert len(imported.json()["imported_purchase_lines"]) == 1
    assert len(purchase_lines.json()["items"]) == 1
    assert {content["name"] for content in evidence_contents} == {
        "PVC pipe",
        "PVC pipe duplicate receipt",
    }


def create_project(client: TestClient):
    return client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()


def create_manual_submission(client: TestClient, project_workspace_id: int):
    return client.post(
        f"/api/project-workspaces/{project_workspace_id}/manual-source-entries",
        json={
            "entry_type": "structured_row",
            "structured_payload": {
                "line_type": "material",
                "name": "PVC pipe",
                "quantity": "20",
                "unit": "pcs",
                "price": "1500",
                "provider_name": "ABC Trading",
                "purchase_date": "2025-07-12",
                "remarks_or_terms": "Delivery included",
            },
        },
    ).json()


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


def add_manual_source_entry(
    client: TestClient,
    *,
    project_workspace_id: int,
    structured_payload: dict,
) -> int:
    from backend.app.sources.models import ManualSourceEntry, SourceSubmission

    with client.app.state.session_factory() as session:
        source_submission = SourceSubmission(
            project_workspace_id=project_workspace_id,
            submission_type="manual_source_entry",
            entered_by=None,
        )
        session.add(source_submission)
        session.flush()
        manual_source_entry = ManualSourceEntry(
            project_workspace_id=project_workspace_id,
            source_submission_id=source_submission.id,
            entry_type="structured_row",
            structured_payload=structured_payload,
            original_text=None,
        )
        session.add(manual_source_entry)
        session.commit()
        return source_submission.id


def approve_candidate(
    client: TestClient,
    *,
    project_workspace_id: int,
    review_batch_id: int,
    candidate_id: int,
    name: str,
):
    return client.post(
        f"/api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/candidates/{candidate_id}/decision",
        json={
            "decision": "approved",
            "reviewed_payload": {
                "line_type": "material",
                "name": name,
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
                "quantity": "20",
                "unit": "pcs",
                "price": "1500",
                "provider_name": "ABC Trading",
            },
        },
    )


def force_candidate_merge_state(
    client: TestClient,
    candidate_id: int,
    *,
    merged_into_candidate_id: int | None,
) -> None:
    from backend.app.review.models import ExtractedCandidate

    with client.app.state.session_factory() as session:
        candidate = session.get(ExtractedCandidate, candidate_id)
        candidate.decision = "merged"
        candidate.status = "merged_for_import"
        candidate.merged_into_candidate_id = merged_into_candidate_id
        session.commit()


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
