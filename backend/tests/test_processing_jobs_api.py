from backend.tests.db import make_postgres_test_client


def make_client(_tmp_path):
    return make_postgres_test_client()


def test_processing_job_list_returns_project_jobs_newest_first(tmp_path):
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

        first = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": "PVC pipe"},
        ).json()
        second = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": "Hauling service"},
        ).json()
        client.post(
            f"/api/project-workspaces/{other_project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": "Other project source"},
        )

        response = client.get(f"/api/project-workspaces/{project['id']}/processing-jobs")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["processing_job"]["id"] for item in items] == [
        second["processing_job"]["id"],
        first["processing_job"]["id"],
    ]
    assert all(
        item["processing_job"]["project_workspace_id"] == project["id"] for item in items
    )
    assert items[0]["source_submission"]["submission_type"] == "manual_source_entry"
