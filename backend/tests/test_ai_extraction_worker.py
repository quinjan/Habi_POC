def create_project(client):
    return client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()


def create_free_form_submission(client, project_workspace_id: int, text: str):
    return client.post(
        f"/api/project-workspaces/{project_workspace_id}/manual-source-entries",
        json={"entry_type": "free_form_text", "original_text": text},
    ).json()


def get_job(client, project_workspace_id: int, processing_job_id: int):
    return client.get(
        f"/api/project-workspaces/{project_workspace_id}/processing-jobs/"
        f"{processing_job_id}"
    ).json()["processing_job"]


class FakeAiProvider:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        self.calls.append((original_text, source_submission_id))
        return {"candidates": self.candidates}


class RaisingAiProvider:
    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        raise RuntimeError("provider unavailable")


def test_ai_candidate_validation_accepts_minimal_valid_purchase_line():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
                "line_type": "material",
                "name": "PVC pipe",
                "price": "1500",
                "currency": "PHP",
                "currency_state": "source_stated",
                "confidence": 0.8,
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ],
    )

    assert len(valid) == 1
    assert dropped == 0


def test_ai_candidate_validation_drops_candidates_without_complete_taxonomy():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
                "line_type": "material",
                "name": "PVC pipe",
                "confidence": 0.8,
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "",
                },
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            },
            {
                "line_type": "service",
                "name": "Hauling",
                "confidence": 0.7,
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            },
        ],
    )

    assert valid == []
    assert dropped == 2


def test_ai_candidate_validation_drops_invalid_candidates():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
                "line_type": "unknown",
                "name": "PVC pipe",
                "confidence": 0.8,
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            },
            {
                "line_type": "service",
                "name": "",
                "confidence": 0.8,
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            },
            {
                "line_type": "material",
                "name": "PVC pipe",
                "confidence": 1.2,
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            },
        ],
    )

    assert valid == []
    assert dropped == 3


def test_ai_candidate_defaults_missing_currency_to_php_when_price_exists():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
                "line_type": "material",
                "name": "PVC pipe",
                "price": "1500",
                "confidence": 0.8,
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ],
    )

    assert dropped == 0
    assert valid[0]["currency"] == "PHP"
    assert valid[0]["currency_state"] == "defaulted"


def test_ai_candidate_preserves_explicit_non_php_iso_currency():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
                "line_type": "material",
                "name": "Imported valve",
                "price": "80",
                "currency": "USD",
                "currency_state": "source_stated",
                "confidence": 0.8,
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ],
    )

    assert dropped == 0
    assert valid[0]["currency"] == "USD"
    assert valid[0]["currency_state"] == "source_stated"


def test_ai_candidate_rejects_partial_dates_and_reasoning_fields():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
                "line_type": "service",
                "name": "Hauling",
                "purchase_date": "2025-07",
                "confidence": 0.8,
                "reasoning": "looks like a hauling service",
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ],
    )

    assert valid == []
    assert dropped == 1


def test_ai_candidate_requires_whole_manual_source_entry_evidence():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
                "line_type": "material",
                "name": "PVC pipe",
                "confidence": 0.8,
                "evidence": {
                    "source_submission_id": 99,
                    "locator": "manual_source_entry.original_text",
                },
            },
            {
                "line_type": "material",
                "name": "PVC elbow",
                "confidence": 0.8,
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.snippet",
                },
            },
        ],
    )

    assert valid == []
    assert dropped == 2


def test_worker_processes_free_form_ai_candidates_with_fake_provider(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(
        client,
        project["id"],
        "PVC pipe and hauling",
    )
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "line_type": "material",
                "name": "PVC pipe",
                "currency": "PHP",
                "currency_state": "source_stated",
                "confidence": 0.8,
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            },
            {
                "line_type": "service",
                "name": "Hauling",
                "currency_state": "unknown",
                "confidence": 0.7,
                "category_suggestion": {
                    "top_level_category": "Services",
                    "subcategory": "Hauling",
                },
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            },
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job['review_batch_id']}"
    ).json()

    assert provider.calls == [("PVC pipe and hauling", source_submission_id)]
    assert job["status"] == "review_ready"
    assert job["started_at"] is not None
    assert job["finished_at"] is not None
    assert job["candidate_count"] == 2
    assert job["diagnostics"] == {
        "processor": "ai_manual_free_form_v1",
        "provider": "fake",
        "model": "fake-ai-provider",
        "raw_candidate_count": 2,
        "valid_candidate_count": 2,
        "dropped_candidate_count": 0,
    }
    assert [candidate["proposed_payload"]["name"] for candidate in review["candidates"]] == [
        "PVC pipe",
        "Hauling",
    ]
    assert review["candidates"][0]["proposed_payload"]["currency_state"] == "source_stated"
    assert review["candidates"][1]["proposed_payload"]["confidence"] == 0.7


def test_free_form_ai_empty_result_marks_no_candidates_found(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(
        client,
        project["id"],
        "Follow up with foreman",
    )
    provider = FakeAiProvider([])

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "no_candidates_found"
    assert job["candidate_count"] == 0
    assert job["review_batch_id"] is None


def test_free_form_ai_keeps_valid_and_drops_invalid_candidates(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(
        client,
        project["id"],
        "PVC pipe and unclear thing",
    )
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "line_type": "material",
                "name": "PVC pipe",
                "currency_state": "unknown",
                "confidence": 0.8,
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            },
            {
                "line_type": "unknown",
                "name": "Unclear thing",
                "confidence": 0.5,
                "evidence": {"source_submission_id": source_submission_id},
            },
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "review_ready"
    assert job["candidate_count"] == 1
    assert job["diagnostics"]["dropped_candidate_count"] == 1


def test_free_form_ai_all_invalid_marks_failed(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "Ambiguous text")
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "line_type": "unknown",
                "name": "Ambiguous",
                "confidence": 0.5,
                "evidence": {"source_submission_id": source_submission_id},
            },
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "failed"
    assert "no valid candidate" in job["error_message"].lower()
    assert job["diagnostics"]["failure_summary"] == "AI extraction produced no valid candidates"


def test_free_form_ai_provider_failure_marks_failed(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "PVC pipe")

    assert run_once(client.app.state.session_factory, ai_provider=RaisingAiProvider()) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "failed"
    assert "provider unavailable" in job["error_message"]
    assert "raw_response" not in job["diagnostics"]
