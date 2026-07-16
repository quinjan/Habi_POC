def create_project(
    client,
    *,
    project_name="Arnaiz Residence Renovation",
    contractor_assigned="Internal",
):
    return client.post(
        "/api/project-workspaces",
        json={
            "project_name": project_name,
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "contractor_assigned": contractor_assigned,
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


class ContextRecordingAiProvider:
    def __init__(self):
        self.memory_context = None

    def extract_purchase_lines(
        self,
        *,
        original_text: str,
        source_submission_id: int,
        memory_context: dict,
    ):
        self.memory_context = memory_context
        return {"candidates": []}


class SequencedFreeFormProvider:
    provider_name = "fake"
    model = "gpt-5.5-test-snapshot"

    def __init__(self, results):
        self.results = list(results)
        self.reasoning_efforts = []
        self.repair_contexts = []

    def extract_purchase_lines(
        self,
        *,
        original_text: str,
        source_submission_id: int,
        memory_context: dict,
        reasoning_effort: str,
        repair_context: dict | None = None,
    ):
        self.reasoning_efforts.append(reasoning_effort)
        self.repair_contexts.append(repair_context)
        return self.results.pop(0)


def test_free_form_worker_confirms_an_initial_empty_result_once(client, monkeypatch):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "true")
    project = create_project(client)
    submission = create_free_form_submission(
        client, project["id"], "No completed purchasing facts were provided."
    )
    provider = SequencedFreeFormProvider(
        [{"candidates": []}, {"candidates": []}]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert provider.reasoning_efforts == ["high", "xhigh"]
    assert provider.repair_contexts == [
        None,
        {"kind": "zero_confirmation", "message": "Confirm that the source has no eligible candidates."},
    ]
    assert job["status"] == "no_candidates_found"
    assert job["candidate_count"] == 0
    assert job["diagnostics"]["attempt_count"] == 2


def test_free_form_worker_marks_a_mixed_batch_retry_as_candidate_local(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "true")
    original_text = "Bought PVC pipe. Final site cleanup completed."
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]

    def candidate(line_type: str, name: str, category: str, annotations=None):
        return {
            "line_type": line_type,
            "name": name,
            "category_suggestion": {
                "top_level_category": "Purchases",
                "subcategory": category,
            },
            "provider_state": "unknown",
            "provider_name": None,
            "confidence": 0.9,
            "evidence": {
                "source_submission_id": source_submission_id,
                "locator": "manual_source_entry.original_text",
            },
            "annotation_proposals": annotations or [],
        }

    material = candidate("material", "PVC pipe", "Pipes")
    invalid_service = candidate(
        "service",
        "Site cleanup",
        "Cleanup",
        [
            {
                "text": "Missing qualifier",
                "annotation_type": "general_qualifier",
                "target": "service",
                "source_excerpt": "not in source",
            }
        ],
    )
    repaired_service = candidate("service", "Site cleanup", "Cleanup")
    provider = SequencedFreeFormProvider(
        [
            {"candidates": [material, invalid_service]},
            {"candidates": [material, repaired_service]},
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert provider.repair_contexts[1]["kind"] == "candidate_local_repair"
    assert provider.repair_contexts[1]["invalid_candidate_count"] == 1
    assert job["status"] == "review_ready"
    assert job["candidate_count"] == 2
    assert job["diagnostics"]["retry_kind"] == "candidate_local_repair"


def test_free_form_annotations_require_exact_quotes_and_receive_character_spans(client):
    from backend.app.processing.worker import run_once

    original_text = (
        "PVC pipe, 20 pcs, from ABC Trading. Delivery included to Makati City. "
        "Payment due in 30 days. Paid already."
    )
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "line_type": "material",
                "name": "PVC pipe",
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
                "provider_state": "external",
                "provider_name": "ABC Trading",
                "confidence": 0.91,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
                "annotation_proposals": [
                    {
                        "text": "Delivery is included to the project site",
                        "annotation_type": "delivery_terms",
                        "target": "purchase_line",
                        "source_excerpt": "Delivery included to Makati City",
                    },
                ],
            }
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1
    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()

    start = original_text.index("Delivery included to Makati City")
    assert review["candidates"][0]["source_grounding"] == {
        "kind": "free_form_text",
        "original_text": original_text,
        "options": [],
    }
    assert review["candidates"][0]["proposed_payload"]["annotation_proposals"] == [
        {
            "proposal_id": "ai:annotation:0",
            "text": "Delivery is included to the project site",
            "annotation_type": "delivery_terms",
            "target": "purchase_line",
            "source_excerpt": "Delivery included to Makati City",
            "source_locator": {
                "kind": "text_span",
                "start": start,
                "end": start + len("Delivery included to Makati City"),
            },
            "provenance": "ai_suggested",
        }
    ]


def seed_material_memory(client, project_workspace_id: int, *, name: str, category: str):
    from backend.app.memory.models import Material, MemoryRecord
    from backend.app.taxonomy.models import TaxonomyNode

    top_level_name, subcategory_name = category.split(" / ")
    with client.app.state.session_factory() as session:
        top_level = TaxonomyNode(
            project_workspace_id=project_workspace_id,
            parent_id=None,
            name=top_level_name,
            normalized_name=top_level_name.casefold(),
        )
        session.add(top_level)
        session.flush()
        subcategory = TaxonomyNode(
            project_workspace_id=project_workspace_id,
            parent_id=top_level.id,
            name=subcategory_name,
            normalized_name=subcategory_name.casefold(),
        )
        session.add(subcategory)
        session.flush()
        record = MemoryRecord(
            project_workspace_id=project_workspace_id,
            record_type="material",
            display_name=name,
            normalized_name=" ".join(name.casefold().split()),
            taxonomy_node_id=subcategory.id,
            status="active",
        )
        session.add(record)
        session.flush()
        session.add(Material(memory_record_id=record.id))
        session.commit()
        return record.id


def seed_many_materials(client, project_workspace_id: int, names: list[str]):
    from backend.app.memory.models import Material, MemoryRecord
    from backend.app.taxonomy.models import TaxonomyNode

    with client.app.state.session_factory() as session:
        top_level = TaxonomyNode(
            project_workspace_id=project_workspace_id,
            parent_id=None,
            name="Materials",
            normalized_name="materials",
        )
        session.add(top_level)
        session.flush()
        subcategory = TaxonomyNode(
            project_workspace_id=project_workspace_id,
            parent_id=top_level.id,
            name="General",
            normalized_name="general",
        )
        session.add(subcategory)
        session.flush()
        for name in names:
            record = MemoryRecord(
                project_workspace_id=project_workspace_id,
                record_type="material",
                display_name=name,
                normalized_name=" ".join(name.casefold().split()),
                taxonomy_node_id=subcategory.id,
                status="active",
            )
            session.add(record)
            session.flush()
            session.add(Material(memory_record_id=record.id))
        session.commit()


def test_ai_extraction_receives_only_selected_project_active_classification_memory(client):
    from backend.app.processing.worker import run_once

    selected_project = create_project(
        client,
        contractor_assigned="Quinlan Construction",
    )
    other_project = create_project(
        client,
        project_name="Ortigas Office Fit-Out",
        contractor_assigned="Other Contractor",
    )
    selected_record_id = seed_material_memory(
        client,
        selected_project["id"],
        name="PVC pipe",
        category="Plumbing / Pipes",
    )
    seed_material_memory(
        client,
        other_project["id"],
        name="Copper wire",
        category="Electrical / Wiring",
    )
    submission = create_free_form_submission(
        client,
        selected_project["id"],
        "Need the prior PVC pipe classification; quantity 20, price PHP 1,500.",
    )
    provider = ContextRecordingAiProvider()

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    assert provider.memory_context == {
        "contractor_assigned": "Quinlan Construction",
        "taxonomy_paths": ["Plumbing / Pipes"],
        "materials": [
            {
                "record_id": selected_record_id,
                "name": "PVC pipe",
                "category_path": "Plumbing / Pipes",
            }
        ],
        "services": [],
        "providers": [],
    }
    serialized_context = str(provider.memory_context)
    assert "Copper wire" not in serialized_context
    assert "20" not in serialized_context
    assert "1500" not in serialized_context
    assert "evidence" not in serialized_context.casefold()


def test_ai_provider_matching_contractor_assigned_defaults_to_internal_before_review(client):
    from backend.app.processing.worker import run_once

    project = create_project(
        client,
        contractor_assigned="  Quinlan   Construction  ",
    )
    submission = create_free_form_submission(
        client,
        project["id"],
        "Quinlan Construction installed the PVC pipe.",
    )
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "linked_concepts": [
                    {
                        "concept_type": "service",
                        "name": "PVC pipe installation",
                        "category_suggestion": {
                            "top_level_category": "Services",
                            "subcategory": "Pipe installation",
                        },
                    }
                ],
                "provider_state": "external",
                "provider_name": "quinlan construction",
                "provider_category_suggestion": {
                    "top_level_category": "Providers",
                    "subcategory": "General",
                },
                "confidence": 0.9,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    candidate = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()["candidates"][0]

    assert candidate["proposed_payload"]["provider_state"] == "internal"
    assert candidate["proposed_payload"]["provider_name"] is None
    assert candidate["proposed_payload"]["provider_memory_record_id"] is None
    assert candidate["proposed_payload"]["observed_provider_text"] == "quinlan construction"


def test_free_form_memory_context_is_complete_and_not_lexically_capped(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    seed_many_materials(
        client,
        project["id"],
        [f"Material {index:03d}" for index in range(101)] + ["Target pipe"],
    )
    submission = create_free_form_submission(client, project["id"], "Target pipe")
    provider = ContextRecordingAiProvider()

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    material_names = [item["name"] for item in provider.memory_context["materials"]]
    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert len(material_names) == 102
    assert material_names[0] == "Material 000"
    assert material_names[-1] == "Target pipe"
    assert job["diagnostics"]["memory_context_record_counts"] == {
        "materials": 102,
        "services": 0,
        "providers": 0,
    }
    assert "memory_context_omitted_counts" not in job["diagnostics"]


def test_free_form_ai_receives_complete_memory_with_explicit_record_ids(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "false")
    project = create_project(client)
    names = [f"Material {index:03d}" for index in range(102)]
    seed_many_materials(client, project["id"], names)
    submission = create_free_form_submission(client, project["id"], "Material 101")
    provider = ContextRecordingAiProvider()

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    materials = provider.memory_context["materials"]

    assert len(materials) == 102
    assert {item["name"] for item in materials} == set(names)
    assert all(isinstance(item["record_id"], int) for item in materials)
    assert job["diagnostics"]["memory_context_record_counts"] == {
        "materials": 102,
        "services": 0,
        "providers": 0,
    }
    assert "memory_context_omitted_counts" not in job["diagnostics"]


def test_free_form_ai_fails_before_model_call_when_complete_memory_exceeds_budget(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_MAX_INPUT_CHARS", "100")
    project = create_project(client)
    seed_many_materials(
        client,
        project["id"],
        ["Very long material vocabulary entry one", "Very long material vocabulary entry two"],
    )
    submission = create_free_form_submission(
        client, project["id"], "Final purchase of material one."
    )
    provider = ContextRecordingAiProvider()

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])

    assert provider.memory_context is None
    assert job["status"] == "failed"
    assert job["candidate_count"] == 0
    assert job["review_batch_id"] is None
    assert "complete selected-project memory exceeds" in job["error_message"].lower()
    assert "no candidates were saved" in job["error_message"].lower()
    assert job["diagnostics"]["estimated_input_chars"] > 100


def test_free_form_ai_rejects_a_cross_project_memory_match(client, monkeypatch):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "false")
    selected_project = create_project(client)
    other_project = create_project(client, project_name="Other project")
    other_record_id = seed_material_memory(
        client,
        other_project["id"],
        name="Eagle Portland Cement",
        category="Civil / Cement",
    )
    original_text = "Final purchase: 10 bags Eagle cement for PHP 8,400."
    submission = create_free_form_submission(
        client, selected_project["id"], original_text
    )
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "linked_concepts": [
                    {
                        "concept_id": "cement",
                        "concept_type": "material",
                        "name": "Eagle Portland Cement",
                        "observed_name_text": "Eagle cement",
                        "project_memory_record_id": other_record_id,
                        "category_suggestion": {
                            "top_level_category": "Civil",
                            "subcategory": "Cement",
                        },
                        "quantity": "10",
                        "unit": "bags",
                        "component_unit_price": None,
                    }
                ],
                "provider_state": "unknown",
                "provider_name": None,
                "observed_provider_text": None,
                "provider_memory_record_id": None,
                "provider_category_suggestion": None,
                "bundle_quantity": None,
                "bundle_unit": None,
                "source_stated_line_total": "8400",
                "currency": "PHP",
                "currency_state": "source_stated",
                "installation_relationships": [],
                "primary_evidence_excerpt": original_text,
                "supporting_evidence_excerpts": [],
                "annotation_proposals": [],
                "confidence": 0.94,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(
        client, selected_project["id"], submission["processing_job"]["id"]
    )

    assert job["status"] == "failed"
    assert job["review_batch_id"] is None
    assert job["candidate_count"] == 0
    assert "no candidates were saved" in job["error_message"].lower()
    assert job["diagnostics"]["validation_failures"] == [
        {
            "candidate_index": 0,
            "reason": "Proposed Material Memory Record was not supplied from the selected project",
            "reason_code": "project_memory_match_not_supplied",
            "record_id": other_record_id,
        }
    ]


def test_free_form_ai_calculates_a_standard_line_total_from_grounded_inputs(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "false")
    original_text = "Final purchase: 10 bags Eagle cement at PHP 840 per bag."
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "linked_concepts": [
                    {
                        "concept_id": "cement",
                        "concept_type": "material",
                        "name": "Eagle Portland Cement",
                        "observed_name_text": "Eagle cement",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Civil",
                            "subcategory": "Cement",
                        },
                        "quantity": "10",
                        "unit": "bags",
                        "component_unit_price": "840",
                    }
                ],
                "provider_state": "unknown",
                "provider_name": None,
                "observed_provider_text": None,
                "provider_memory_record_id": None,
                "provider_category_suggestion": None,
                "bundle_quantity": None,
                "bundle_unit": None,
                "source_stated_line_total": None,
                "currency": "PHP",
                "currency_state": "source_stated",
                "installation_relationships": [],
                "primary_evidence_excerpt": original_text,
                "supporting_evidence_excerpts": [],
                "annotation_proposals": [],
                "confidence": 0.94,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()
    payload = review["candidates"][0]["proposed_payload"]

    assert payload["price"] == "8400"
    assert payload["price_state"] == "calculated"
    assert payload["calculation"] == {
        "formula": "quantity × unit price",
        "quantity": "10",
        "unit": "bags",
        "unit_price": "840",
        "result": "8400",
    }


def test_free_form_ai_preserves_source_total_and_surfaces_an_unexplained_variance(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "false")
    original_text = (
        "Final purchase: 10 bags Eagle cement at PHP 840 per bag; total PHP 8,300."
    )
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "linked_concepts": [
                    {
                        "concept_id": "cement",
                        "concept_type": "material",
                        "name": "Eagle Portland Cement",
                        "observed_name_text": "Eagle cement",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Civil",
                            "subcategory": "Cement",
                        },
                        "quantity": "10",
                        "unit": "bags",
                        "component_unit_price": "840",
                    }
                ],
                "provider_state": "unknown",
                "provider_name": None,
                "observed_provider_text": None,
                "provider_memory_record_id": None,
                "provider_category_suggestion": None,
                "bundle_quantity": None,
                "bundle_unit": None,
                "source_stated_line_total": "8300",
                "currency": "PHP",
                "currency_state": "source_stated",
                "installation_relationships": [],
                "primary_evidence_excerpt": original_text,
                "supporting_evidence_excerpts": [],
                "annotation_proposals": [],
                "confidence": 0.94,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()
    payload = review["candidates"][0]["proposed_payload"]

    assert payload["price"] == "8300"
    assert payload["price_state"] == "source_stated"
    assert payload["calculation"]["result"] == "8400"
    assert payload["variance_warning"] == {
        "calculated_total": "8400",
        "source_stated_total": "8300",
        "variance": "-100",
    }
    assert payload["annotation_proposals"] == []


def test_candidate_review_saves_repeated_concept_controls_with_immutable_observed_text(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "false")
    original_text = (
        "Completed works: Acme supplied steel doors and aluminum windows and installed "
        "both for PHP 150,000."
    )
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "linked_concepts": [
                    {
                        "concept_id": "doors",
                        "concept_type": "material",
                        "name": "Steel door",
                        "observed_name_text": "steel doors",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Architectural",
                            "subcategory": "Doors",
                        },
                    },
                    {
                        "concept_id": "windows",
                        "concept_type": "material",
                        "name": "Aluminum window",
                        "observed_name_text": "aluminum windows",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Architectural",
                            "subcategory": "Windows",
                        },
                    },
                    {
                        "concept_id": "installation",
                        "concept_type": "service",
                        "name": "Door and window installation",
                        "observed_name_text": "installed both",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Services",
                            "subcategory": "Installation",
                        },
                    },
                ],
                "provider_state": "external",
                "provider_name": "Acme",
                "observed_provider_text": "Acme",
                "provider_memory_record_id": None,
                "provider_category_suggestion": {
                    "top_level_category": "Providers",
                    "subcategory": "Supply and installation",
                },
                "source_stated_line_total": "150000",
                "currency": "PHP",
                "currency_state": "source_stated",
                "installation_relationships": [
                    {
                        "service_concept_id": "installation",
                        "material_concept_ids": ["doors", "windows"],
                        "source_excerpt": "installed both",
                    }
                ],
                "primary_evidence_excerpt": original_text,
                "supporting_evidence_excerpts": [],
                "annotation_proposals": [],
                "confidence": 0.96,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )
    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1
    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()
    candidate = review["candidates"][0]
    proposed = candidate["proposed_payload"]
    reviewed_concepts = [
        {
            "concept_id": concept["concept_id"],
            "concept_type": concept["concept_type"],
            "name": (
                "Window installation"
                if concept["concept_id"] == "installation"
                else concept["name"]
            ),
            "observed_name_text": concept["observed_name_text"],
            "project_memory_record_id": concept["project_memory_record_id"],
            "top_level_category": concept["category_suggestion"][
                "top_level_category"
            ],
            "subcategory": concept["category_suggestion"]["subcategory"],
            "quantity": concept["quantity"],
            "unit": concept["unit"],
            "component_unit_price": concept["component_unit_price"],
        }
        for concept in proposed["linked_concepts"]
    ]

    response = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
        f"/candidates/{candidate['id']}/decision",
        json={
            "decision": "approved",
            "reviewed_payload": {
                "linked_concepts": reviewed_concepts,
                "provider_state": "external",
                "provider_name": "Acme",
                "observed_provider_text": "Acme",
                "provider_memory_record_id": None,
                "provider_top_level_category": "Providers",
                "provider_subcategory": "Supply and installation",
                "bundle_quantity": None,
                "bundle_unit": None,
                "price": "150000",
                "price_state": "source_stated",
                "currency": "PHP",
                "installation_relationships": proposed[
                    "installation_relationships"
                ],
                "primary_evidence_span": proposed["primary_evidence_span"],
                "supporting_evidence_spans": proposed["supporting_evidence_spans"],
                "annotation_proposals": [],
            },
        },
    )

    assert response.status_code == 200
    reviewed = response.json()["reviewed_payload"]
    assert len(reviewed["linked_concepts"]) == 3
    assert [concept["observed_name_text"] for concept in reviewed["linked_concepts"]] == [
        "steel doors",
        "aluminum windows",
        "installed both",
    ]
    assert reviewed["linked_concepts"][2]["name"] == "Window installation"


def test_candidate_review_exposes_memory_aware_options_and_skips_gate_for_explicit_match(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "false")
    project = create_project(client)
    matched_record_id = seed_material_memory(
        client,
        project["id"],
        name="Eagle Portland Cement",
        category="Civil / Cement",
    )
    other_record_id = seed_material_memory(
        client,
        project["id"],
        name="Premium Portland Cement",
        category="Materials / Specialty Cement",
    )
    original_text = "Final purchase: 10 bags Eagle cement for PHP 8,400."
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "linked_concepts": [
                    {
                        "concept_id": "cement",
                        "concept_type": "material",
                        "name": "Eagle Portland Cement",
                        "observed_name_text": "Eagle cement",
                        "project_memory_record_id": matched_record_id,
                        "category_suggestion": {
                            "top_level_category": "Civil",
                            "subcategory": "Cement",
                        },
                    }
                ],
                "provider_state": "unknown",
                "provider_name": None,
                "observed_provider_text": None,
                "provider_memory_record_id": None,
                "provider_category_suggestion": None,
                "source_stated_line_total": "8400",
                "currency": "PHP",
                "currency_state": "source_stated",
                "installation_relationships": [],
                "primary_evidence_excerpt": original_text,
                "supporting_evidence_excerpts": [],
                "annotation_proposals": [],
                "confidence": 0.94,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    candidate = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()["candidates"][0]

    assert candidate["taxonomy_gates"] == []
    assert candidate["memory_options"] == [
        {
            "record_id": matched_record_id,
            "subject_type": "material",
            "subject_name": "Eagle Portland Cement",
            "category_path": "Civil / Cement",
            "provider_roles": [],
        },
        {
            "record_id": other_record_id,
            "subject_type": "material",
            "subject_name": "Premium Portland Cement",
            "category_path": "Materials / Specialty Cement",
            "provider_roles": [],
        },
    ]


def test_reset_candidate_restores_review_baseline_without_changing_outcome_or_calling_ai(
    client,
):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(
        client, project["id"], "Final purchase: PVC pipe."
    )
    source_submission_id = submission["source_submission"]["id"]
    provider = FakeAiProvider(
        [
            {
                "line_type": "material",
                "name": "PVC pipe",
                "category_suggestion": {
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                },
                "provider_state": "unknown",
                "confidence": 0.8,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )
    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1
    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()
    candidate = review["candidates"][0]
    decision = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
        f"/candidates/{candidate['id']}/decision",
        json={
            "decision": "approved",
            "reviewed_payload": {
                "line_type": "material",
                "name": "PVC pressure pipe",
                "top_level_category": "Plumbing",
                "subcategory": "Pressure pipes",
                "provider_state": "unknown",
            },
        },
    )
    assert decision.status_code == 200

    reset = client.post(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
        f"/candidates/{candidate['id']}/reset"
    )

    assert reset.status_code == 200
    reset_candidate = reset.json()
    assert reset_candidate["decision"] == "approved"
    assert reset_candidate["reviewed_payload"] is None
    assert reset_candidate["proposed_payload"]["name"] == "PVC pipe"
    assert provider.calls == [("Final purchase: PVC pipe.", source_submission_id)]


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


def test_ai_candidate_validation_accepts_bundled_concepts_and_provider_state():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {
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
                "currency_state": "unknown",
                "confidence": 0.8,
                "evidence": {
                    "source_submission_id": 10,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ],
    )

    assert dropped == 0
    assert [concept["concept_type"] for concept in valid[0]["linked_concepts"]] == [
        "material",
        "service",
    ]
    assert valid[0]["provider_state"] == "external"


def test_free_form_worker_persists_a_grounded_multi_concept_installation_bundle(client):
    from backend.app.processing.worker import run_once

    original_text = (
        "Completed works — Acme supplied ten steel doors and five aluminum windows, "
        "then installed all doors and windows as one package for PHP 150,000."
    )
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    primary_excerpt = (
        "Acme supplied ten steel doors and five aluminum windows, then installed all "
        "doors and windows as one package for PHP 150,000"
    )
    provider = FakeAiProvider(
        [
            {
                "linked_concepts": [
                    {
                        "concept_id": "steel-doors",
                        "concept_type": "material",
                        "name": "Steel door",
                        "observed_name_text": "steel doors",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Architectural",
                            "subcategory": "Doors",
                        },
                        "quantity": "10",
                        "unit": "units",
                        "component_unit_price": None,
                    },
                    {
                        "concept_id": "aluminum-windows",
                        "concept_type": "material",
                        "name": "Aluminum window",
                        "observed_name_text": "aluminum windows",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Architectural",
                            "subcategory": "Windows",
                        },
                        "quantity": "5",
                        "unit": "units",
                        "component_unit_price": None,
                    },
                    {
                        "concept_id": "installation",
                        "concept_type": "service",
                        "name": "Door and window installation",
                        "observed_name_text": "installed all doors and windows",
                        "project_memory_record_id": None,
                        "category_suggestion": {
                            "top_level_category": "Services",
                            "subcategory": "Installation",
                        },
                        "quantity": None,
                        "unit": None,
                        "component_unit_price": None,
                    },
                ],
                "provider_state": "external",
                "provider_name": "Acme",
                "observed_provider_text": "Acme",
                "provider_memory_record_id": None,
                "provider_category_suggestion": {
                    "top_level_category": "Providers",
                    "subcategory": "Supply and installation",
                },
                "bundle_quantity": "1",
                "bundle_unit": "package",
                "source_stated_line_total": "150000",
                "currency": "PHP",
                "currency_state": "source_stated",
                "installation_relationships": [
                    {
                        "service_concept_id": "installation",
                        "material_concept_ids": ["steel-doors", "aluminum-windows"],
                        "source_excerpt": "installed all doors and windows",
                    }
                ],
                "primary_evidence_excerpt": primary_excerpt,
                "supporting_evidence_excerpts": ["Completed works"],
                "annotation_proposals": [],
                "confidence": 0.96,
                "evidence": {
                    "source_submission_id": source_submission_id,
                    "locator": "manual_source_entry.original_text",
                },
            }
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()
    payload = review["candidates"][0]["proposed_payload"]
    primary_start = original_text.index(primary_excerpt)
    supporting_start = original_text.index("Completed works")

    assert job["status"] == "review_ready"
    assert payload["line_type"] == "bundled"
    assert len(payload["linked_concepts"]) == 3
    assert payload["primary_evidence_span"] == {
        "excerpt": primary_excerpt,
        "start": primary_start,
        "end": primary_start + len(primary_excerpt),
    }
    assert payload["supporting_evidence_spans"] == [
        {
            "excerpt": "Completed works",
            "start": supporting_start,
            "end": supporting_start + len("Completed works"),
        }
    ]
    assert payload["installation_relationships"] == [
        {
            "service_concept_id": "installation",
            "material_concept_ids": ["steel-doors", "aluminum-windows"],
            "source_excerpt": "installed all doors and windows",
            "source_locator": {
                "kind": "text_span",
                "start": original_text.index("installed all doors and windows"),
                "end": original_text.index("installed all doors and windows")
                + len("installed all doors and windows"),
            },
        }
    ]


def test_free_form_worker_retries_one_invalid_result_and_persists_only_the_repair(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "true")
    original_text = "Final purchase: 10 bags Eagle cement from Wilcon for PHP 8,400."
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    candidate = {
        "linked_concepts": [
            {
                "concept_id": "cement",
                "concept_type": "material",
                "name": "Eagle Portland Cement",
                "observed_name_text": "Eagle cement",
                "project_memory_record_id": None,
                "category_suggestion": {
                    "top_level_category": "Civil",
                    "subcategory": "Cement",
                },
                "quantity": "10",
                "unit": "bags",
                "component_unit_price": None,
            }
        ],
        "provider_state": "external",
        "provider_name": "Wilcon",
        "observed_provider_text": "Wilcon",
        "provider_memory_record_id": None,
        "provider_category_suggestion": {
            "top_level_category": "Providers",
            "subcategory": "Material suppliers",
        },
        "bundle_quantity": None,
        "bundle_unit": None,
        "source_stated_line_total": "8400",
        "currency": "PHP",
        "currency_state": "source_stated",
        "installation_relationships": [],
        "primary_evidence_excerpt": original_text.removesuffix("."),
        "supporting_evidence_excerpts": [],
        "annotation_proposals": [],
        "confidence": 0.94,
        "evidence": {
            "source_submission_id": source_submission_id,
            "locator": "manual_source_entry.original_text",
        },
    }
    invalid_candidate = {**candidate, "primary_evidence_excerpt": "not in source"}
    provider = SequencedFreeFormProvider(
        [{"candidates": [invalid_candidate]}, {"candidates": [candidate]}]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()

    assert provider.reasoning_efforts == ["high", "xhigh"]
    assert job["status"] == "review_ready"
    assert job["candidate_count"] == 1
    assert job["diagnostics"]["attempt_count"] == 2
    assert review["candidates"][0]["proposed_payload"]["primary_evidence_excerpt"] == (
        original_text.removesuffix(".")
    )


def test_free_form_worker_fails_atomically_with_safe_grounding_detail_when_retries_are_disabled(
    client, monkeypatch
):
    from backend.app.processing.worker import run_once

    monkeypatch.setenv("OPENAI_FREE_FORM_RETRIES_ENABLED", "false")
    original_text = (
        "Final purchase: 10 bags Eagle cement from Wilcon for PHP 8,400. Paid already."
    )
    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], original_text)
    source_submission_id = submission["source_submission"]["id"]
    provider = SequencedFreeFormProvider(
        [
            {
                "candidates": [
                    {
                        "linked_concepts": [
                            {
                                "concept_id": "cement",
                                "concept_type": "material",
                                "name": "Eagle Portland Cement",
                                "observed_name_text": "Eagle cement",
                                "project_memory_record_id": None,
                                "category_suggestion": {
                                    "top_level_category": "Civil",
                                    "subcategory": "Cement",
                                },
                                "quantity": "10",
                                "unit": "bags",
                                "component_unit_price": None,
                            }
                        ],
                        "provider_state": "external",
                        "provider_name": "Wilcon",
                        "observed_provider_text": "Wilcon",
                        "provider_memory_record_id": None,
                        "provider_category_suggestion": {
                            "top_level_category": "Providers",
                            "subcategory": "Material suppliers",
                        },
                        "bundle_quantity": None,
                        "bundle_unit": None,
                        "source_stated_line_total": "8400",
                        "currency": "PHP",
                        "currency_state": "source_stated",
                        "installation_relationships": [],
                        "primary_evidence_excerpt": original_text,
                        "supporting_evidence_excerpts": [],
                        "annotation_proposals": [
                            {
                                "text": "Paid already",
                                "annotation_type": "general_qualifier",
                                "target": "purchase_line",
                                "source_excerpt": "Paid already",
                            }
                        ],
                        "confidence": 0.94,
                        "evidence": {
                            "source_submission_id": source_submission_id,
                            "locator": "manual_source_entry.original_text",
                        },
                    }
                ]
            },
            {"candidates": []},
        ]
    )

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    paid_start = original_text.index("Paid already")

    assert provider.reasoning_efforts == ["high"]
    assert job["status"] == "failed"
    assert job["candidate_count"] == 0
    assert job["review_batch_id"] is None
    assert "no candidates were saved" in job["error_message"].lower()
    assert job["diagnostics"]["validation_failures"] == [
        {
            "candidate_index": 0,
            "source_excerpt": "Paid already",
            "source_locator": {
                "kind": "text_span",
                "start": paid_start,
                "end": paid_start + len("Paid already"),
            },
            "reason": "Annotation contains workflow noise",
        }
    ]


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
    assert job["diagnostics"]["processor"] == "ai_manual_free_form_v1"
    assert job["diagnostics"]["provider"] == "fake"
    assert job["diagnostics"]["model"] == "fake-ai-provider"
    assert job["diagnostics"]["raw_candidate_count"] == 2
    assert job["diagnostics"]["valid_candidate_count"] == 2
    assert job["diagnostics"]["dropped_candidate_count"] == 0
    assert job["diagnostics"]["memory_context_record_counts"] == {
        "materials": 0,
        "services": 0,
        "providers": 0,
    }
    assert job["diagnostics"]["estimated_input_chars"] > len("PVC pipe and hauling")
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


def test_free_form_ai_fails_atomically_when_any_candidate_is_invalid(client):
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
    assert job["status"] == "failed"
    assert job["candidate_count"] == 0
    assert job["review_batch_id"] is None
    assert job["diagnostics"]["dropped_candidate_count"] == 1
    assert "no candidates were saved" in job["error_message"].lower()


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
    assert "complete grounded review batch" in job["error_message"].lower()
    assert "no candidates were saved" in job["error_message"].lower()
    assert job["diagnostics"]["invalid_candidate_count"] == 1


def test_free_form_ai_provider_failure_marks_failed(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "PVC pipe")

    assert run_once(client.app.state.session_factory, ai_provider=RaisingAiProvider()) == 1

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "failed"
    assert "provider unavailable" in job["error_message"]
    assert "raw_response" not in job["diagnostics"]
