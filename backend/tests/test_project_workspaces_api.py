def test_reviewer_can_create_project_workspace_with_completed_project_context(client):
    response = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "floor_area": "180 sqm",
            "trade_scopes": ["Plumbing", "Electrical"],
            "client_or_owner": "Arnaiz family",
            "notes": "Completed project workspace for purchasing memory review.",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "project_name": "Arnaiz Residence Renovation",
        "project_type": "Residential renovation",
        "location": "Makati City",
        "completion_date": None,
        "completion_year": 2025,
        "floor_area": "180 sqm",
        "trade_scopes": ["Plumbing", "Electrical"],
        "client_or_owner": "Arnaiz family",
        "notes": "Completed project workspace for purchasing memory review.",
    }


def test_reviewer_can_list_project_workspace_names_for_selection(client):
    client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    )
    client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Ortigas Office Fit-Out",
            "project_type": "Commercial fit-out",
            "location": "Pasig City",
            "completion_year": 2024,
        },
    )

    response = client.get("/api/project-workspaces")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"id": 1, "project_name": "Arnaiz Residence Renovation"},
            {"id": 2, "project_name": "Ortigas Office Fit-Out"},
        ]
    }


def test_selected_project_workspace_opens_scoped_empty_purchase_lines_view(client):
    first_project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()
    second_project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Ortigas Office Fit-Out",
            "project_type": "Commercial fit-out",
            "location": "Pasig City",
            "completion_year": 2024,
        },
    ).json()

    response = client.get(
        f"/api/project-workspaces/{second_project['id']}/purchase-lines"
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_workspace": {
            "id": second_project["id"],
            "project_name": "Ortigas Office Fit-Out",
        },
        "items": [],
    }
    assert first_project["project_name"] not in str(response.json())
