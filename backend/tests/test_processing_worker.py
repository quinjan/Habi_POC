def test_worker_run_once_returns_zero_when_no_jobs(client):
    from backend.app.processing.worker import run_once

    processed = run_once(client.app.state.session_factory)

    assert processed == 0


def test_worker_processes_structured_row_job_to_review_ready(client):
    from backend.app.processing.worker import run_once

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
            },
        },
    ).json()

    assert run_once(client.app.state.session_factory) == 1
    job_detail = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()

    assert job_detail["processing_job"]["status"] == "review_ready"
    assert job_detail["processing_job"]["candidate_count"] == 1
    assert job_detail["processing_job"]["diagnostics"] == {
        "processor": "structured_manual_row_v1"
    }
    assert job_detail["processing_job"]["finished_at"] is not None
    assert job_detail["review_batch_id"] is not None
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/"
        f"{job_detail['review_batch_id']}"
    ).json()
    assert review["candidates"][0]["proposed_payload"]["name"] == "PVC pipe"


def test_worker_module_exposes_once_and_loop_commands():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "backend.app.processing", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--once" in result.stdout
    assert "--loop" in result.stdout


def test_worker_run_once_processes_only_one_queued_job(client):
    from backend.app.processing.worker import run_once

    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()
    for name in ["PVC pipe", "Hauling"]:
        client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={
                "entry_type": "structured_row",
                "structured_payload": {
                    "line_type": "material",
                    "name": name,
                },
            },
        )

    assert run_once(client.app.state.session_factory) == 1
    jobs = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs"
    ).json()["items"]
    statuses = [item["processing_job"]["status"] for item in jobs]

    assert statuses.count("review_ready") == 1
    assert statuses.count("queued") == 1


def test_worker_run_once_skips_ai_free_form_jobs_without_provider(client):
    from backend.app.processing.worker import run_once

    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()
    free_form_submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={
            "entry_type": "free_form_text",
            "original_text": "Hauling service by ABC Trading",
        },
    ).json()
    structured_submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={
            "entry_type": "structured_row",
            "structured_payload": {
                "line_type": "material",
                "name": "PVC pipe",
            },
        },
    ).json()

    assert run_once(client.app.state.session_factory) == 1

    free_form_job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{free_form_submission['processing_job']['id']}"
    ).json()
    structured_job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{structured_submission['processing_job']['id']}"
    ).json()
    assert free_form_job["processing_job"]["status"] == "queued"
    assert structured_job["processing_job"]["status"] == "review_ready"


def test_worker_review_ready_output_remains_project_scoped(client):
    from backend.app.processing.worker import run_once

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
            "project_name": "Ortigas Office Fitout",
            "project_type": "Commercial fitout",
            "location": "Pasig City",
            "completion_year": 2024,
        },
    ).json()
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={
            "entry_type": "structured_row",
            "structured_payload": {
                "line_type": "material",
                "name": "PVC pipe",
            },
        },
    ).json()

    assert run_once(client.app.state.session_factory) == 1
    job_detail = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()

    assert (
        client.get(
            f"/api/project-workspaces/{other_project['id']}/review-batches/"
            f"{job_detail['review_batch_id']}"
        ).status_code
        == 404
    )
