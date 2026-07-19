def create_project(client):
    return client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "contractor_assigned": "Internal",
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


def valid_candidate(source_submission_id: int):
    return {
        "line_type": "material",
        "name": "PVC pipe",
        "currency_state": "unknown",
        "confidence": 0.8,
        "evidence": {
            "source_submission_id": source_submission_id,
            "locator": "manual_source_entry.original_text",
        },
    }


class FakeAiProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, candidates):
        self.candidates = candidates

    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        return {"candidates": self.candidates}


def test_openai_provider_config_requires_api_key(monkeypatch):
    from backend.app.processing.openai_provider import OpenAiProviderConfig

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-nano")

    try:
        OpenAiProviderConfig.from_env()
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing OPENAI_API_KEY to fail")


def test_openai_provider_config_defaults_model_to_nano(monkeypatch):
    from backend.app.processing.openai_provider import OpenAiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    config = OpenAiProviderConfig.from_env()

    assert config.model == "gpt-5.4-nano"


def test_openai_provider_config_separates_free_form_model_and_reasoning(monkeypatch):
    from backend.app.processing.openai_provider import OpenAiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "xlsx-model")
    monkeypatch.delenv("OPENAI_FREE_FORM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_FREE_FORM_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("OPENAI_FREE_FORM_RETRY_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("OPENAI_FREE_FORM_RETRIES_ENABLED", raising=False)

    config = OpenAiProviderConfig.from_env()

    assert config.model == "xlsx-model"
    assert config.free_form_model == "gpt-5.5-2026-04-23"
    assert config.free_form_reasoning_effort == "high"
    assert config.free_form_retry_reasoning_effort == "xhigh"
    assert config.free_form_retries_enabled is True


def test_openai_provider_config_stores_responses_by_default_and_allows_disabling(
    monkeypatch,
):
    from backend.app.processing.openai_provider import OpenAiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("HABI_OPENAI_STORE_RESPONSES", raising=False)

    assert OpenAiProviderConfig.from_env().store_responses is True

    monkeypatch.setenv("HABI_OPENAI_STORE_RESPONSES", "false")

    assert OpenAiProviderConfig.from_env().store_responses is False


def test_openai_provider_config_can_disable_client_transport_retries(monkeypatch):
    from backend.app.processing.openai_provider import OpenAiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_CLIENT_MAX_RETRIES", "0")

    assert OpenAiProviderConfig.from_env().client_max_retries == 0


def test_openai_provider_config_ignores_blank_base_url(monkeypatch):
    from backend.app.processing.openai_provider import OpenAiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "")

    config = OpenAiProviderConfig.from_env()

    assert config.base_url is None


def test_openai_provider_uses_default_base_url_when_env_base_url_is_blank(monkeypatch):
    import openai

    from backend.app.processing.openai_provider import (
        OpenAiExtractionProvider,
        OpenAiProviderConfig,
    )

    calls = {}

    class DummyOpenAiClient:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.setattr(openai, "OpenAI", DummyOpenAiClient)

    OpenAiExtractionProvider(OpenAiProviderConfig(api_key="test-key", base_url=None))

    assert calls["kwargs"]["base_url"] == "https://api.openai.com/v1"
    assert calls["kwargs"]["max_retries"] == 2


def test_worker_provider_factory_failure_does_not_claim_queued_job(client):
    from backend.app.processing.worker import run_once

    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
            "contractor_assigned": "Internal",
        },
    ).json()
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={"entry_type": "free_form_text", "original_text": "PVC pipe"},
    ).json()

    def failing_factory():
        raise RuntimeError("OPENAI_API_KEY is required")

    try:
        run_once(
            client.app.state.session_factory,
            ai_provider_factory=failing_factory,
        )
    except RuntimeError:
        pass

    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/"
        f"{submission['processing_job']['id']}"
    ).json()["processing_job"]
    assert job["status"] == "queued"


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "Response",
            (),
            {
                "output_parsed": {"candidates": []},
                "usage": type("Usage", (), {"input_tokens": 10, "output_tokens": 5})(),
            },
        )()


class FakeOpenAiClient:
    def __init__(self):
        self.responses = FakeResponses()


class SequencedResponses:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        return type("Response", (), {"output_parsed": output})()


class SequencedOpenAiClient:
    def __init__(self, outputs):
        self.responses = SequencedResponses(outputs)


class UnusableResponseFakeResponses(FakeResponses):
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_parsed": None})()


class UnusableResponseFakeOpenAiClient:
    def __init__(self):
        self.responses = UnusableResponseFakeResponses()


class OutputTextFakeResponses(FakeResponses):
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "Response",
            (),
            {"output_parsed": None, "output_text": '{"candidates": []}'},
        )()


class OutputTextFakeOpenAiClient:
    def __init__(self):
        self.responses = OutputTextFakeResponses()


class RuntimeFailingProvider:
    provider_name = "openai"
    model = "gpt-5.4-nano"

    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        raise RuntimeError("OpenAI API unavailable")


class MalformedResultProvider:
    provider_name = "openai"
    model = "gpt-5.4-nano"

    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        return None


def test_openai_provider_requests_strict_structured_output():
    from backend.app.processing.openai_provider import (
        OpenAiExtractionProvider,
        OpenAiProviderConfig,
    )

    client = FakeOpenAiClient()
    provider = OpenAiExtractionProvider(
        config=OpenAiProviderConfig(api_key="test-key", model="gpt-5.4-nano"),
        client=client,
    )

    provider.extract_purchase_lines(
        original_text="PVC pipe",
        source_submission_id=123,
        memory_context={
            "contractor_assigned": "Quinlan Construction",
            "taxonomy_paths": ["Plumbing / Pipes"],
            "materials": [],
            "services": [],
            "providers": [],
        },
    )

    call = client.responses.calls[0]
    assert call["model"] == "gpt-5.5-2026-04-23"
    assert call["reasoning"] == {"effort": "high"}
    assert "text" in call
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    candidate_schema = call["text"]["format"]["schema"]["properties"]["candidates"][
        "items"
    ]
    assert "linked_concepts" in candidate_schema["properties"]
    assert "provider_state" in candidate_schema["properties"]
    annotation_schema = candidate_schema["properties"]["annotation_proposals"]["items"]
    assert annotation_schema["properties"]["annotation_type"]["enum"] == [
        "delivery_terms",
        "payment_terms",
        "validity_terms",
        "warranty_terms",
        "availability_terms",
        "condition_or_exclusion",
        "general_qualifier",
    ]
    assert annotation_schema["properties"]["target"]["enum"] == [
        "purchase_line",
        "material",
        "service",
        "provider",
    ]
    assert "Quinlan Construction" in call["input"][1]["content"]
    system_prompt = call["input"][0]["content"].lower()
    assert "case-and-whitespace normalization" in system_prompt
    assert "contractor assigned" in system_prompt
    assert "exact quote" in system_prompt


def test_free_form_openai_request_uses_gpt55_grounded_multi_concept_contract():
    from backend.app.processing.openai_provider import (
        OpenAiExtractionProvider,
        OpenAiProviderConfig,
    )

    client = FakeOpenAiClient()
    provider = OpenAiExtractionProvider(
        config=OpenAiProviderConfig(
            api_key="test-key",
            model="xlsx-model",
            free_form_model="gpt-5.5-2026-04-23",
        ),
        client=client,
    )

    provider.extract_purchase_lines(
        original_text="Completed works: Acme supplied and installed steel doors.",
        source_submission_id=123,
        memory_context={
            "contractor_assigned": "Quinlan Construction",
            "taxonomy_paths": ["Architectural / Doors"],
            "materials": [],
            "services": [],
            "providers": [],
        },
        reasoning_effort="xhigh",
    )

    call = client.responses.calls[0]
    candidate_schema = call["text"]["format"]["schema"]["properties"]["candidates"][
        "items"
    ]
    concept_schema = candidate_schema["properties"]["linked_concepts"]
    concept_properties = concept_schema["items"]["properties"]
    candidate_properties = candidate_schema["properties"]
    system_prompt = call["input"][0]["content"].lower()

    assert call["model"] == "gpt-5.5-2026-04-23"
    assert call["reasoning"] == {"effort": "xhigh"}
    assert "maxItems" not in concept_schema
    assert {
        "concept_id",
        "observed_name_text",
        "project_memory_record_id",
        "quantity",
        "unit",
        "component_unit_price",
    }.issubset(concept_properties)
    assert {
        "observed_provider_text",
        "provider_memory_record_id",
        "bundle_quantity",
        "bundle_unit",
        "source_stated_line_total",
        "primary_evidence_excerpt",
        "supporting_evidence_excerpts",
        "installation_relationships",
    }.issubset(candidate_properties)
    assert "line_type" not in candidate_properties
    assert "candidate-local non-final" in system_prompt
    assert "worked-on object" in system_prompt
    assert "ambiguous target" in system_prompt
    assert "workflow" in system_prompt
    assert "identity-defining source details" in system_prompt
    assert "normalize punctuation" in system_prompt
    assert "transaction or lifecycle qualifiers" in system_prompt
    assert "copy its supplied canonical name and category exactly" in system_prompt
    assert "return a null record id" in system_prompt


def test_openai_provider_uses_stateless_strict_xlsx_profile_and_extraction_calls():
    from backend.app.processing.openai_provider import (
        OpenAiExtractionProvider,
        OpenAiProviderConfig,
    )

    profile = {
        "worksheet_name": "Purchases",
        "title_rows": [],
        "header_rows": [1],
        "regions": [],
    }
    extraction = {"candidates": []}
    client = SequencedOpenAiClient([profile, extraction])
    provider = OpenAiExtractionProvider(
        config=OpenAiProviderConfig(api_key="test-key", model="gpt-5.4-nano"),
        client=client,
    )
    worksheet = {
        "worksheet": {"name": "Purchases", "index": 0, "merged_ranges": []},
        "cells": [],
    }

    assert provider.profile_worksheet(
        worksheet=worksheet, source_submission_id=123
    ) == profile
    assert provider.extract_worksheet_chunk(
        profile=profile,
        region={"region_id": "purchases"},
        rows=[],
        context_rows=[],
        source_submission_id=123,
    ) == extraction

    assert len(client.responses.calls) == 2
    profile_prompt = client.responses.calls[0]["input"][0]["content"].lower()
    assert "map every available extraction field" in profile_prompt
    assert "without mapped columns must be marked unusable" in profile_prompt
    profile_column_schema = client.responses.calls[0]["text"]["format"]["schema"][
        "properties"
    ]["regions"]["items"]["properties"]["columns"]["properties"]
    assert {
        "unit_price",
        "material_name",
        "material_category",
        "service_name",
        "service_category",
        "provider_state",
        "provider_category",
    }.issubset(profile_column_schema)
    extraction_prompt = client.responses.calls[1]["input"][0]["content"].lower()
    assert "case-and-whitespace normalization" in extraction_prompt
    assert "contractor assigned" in extraction_prompt
    assert "every clearly reviewable body row" in extraction_prompt
    assert "never replace" in extraction_prompt
    assert "source provider name" in extraction_prompt
    for call in client.responses.calls:
        assert call["model"] == "gpt-5.4-nano"
        assert call["store"] is True
        assert call["text"]["format"]["type"] == "json_schema"
        assert call["text"]["format"]["strict"] is True
        assert "previous_response_id" not in call
        assert "conversation" not in call


def test_openai_provider_rejects_unusable_structured_response():
    from backend.app.processing.openai_provider import (
        OpenAiExtractionProvider,
        OpenAiProviderConfig,
    )

    provider = OpenAiExtractionProvider(
        config=OpenAiProviderConfig(api_key="test-key", model="gpt-5.4-nano"),
        client=UnusableResponseFakeOpenAiClient(),
    )

    try:
        provider.extract_purchase_lines(original_text="PVC pipe", source_submission_id=123)
    except RuntimeError as exc:
        assert "usable structured output" in str(exc)
    else:
        raise AssertionError("Expected unusable OpenAI response to fail")


def test_openai_provider_accepts_json_output_text_when_parsed_output_is_absent():
    from backend.app.processing.openai_provider import (
        OpenAiExtractionProvider,
        OpenAiProviderConfig,
    )

    provider = OpenAiExtractionProvider(
        config=OpenAiProviderConfig(api_key="test-key", model="gpt-5.4-nano"),
        client=OutputTextFakeOpenAiClient(),
    )

    result = provider.extract_purchase_lines(original_text="PVC pipe", source_submission_id=123)

    assert result == {"candidates": []}


def test_openai_runtime_failure_marks_job_failed(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "PVC pipe")

    run_once(client.app.state.session_factory, ai_provider=RuntimeFailingProvider())

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "failed"
    assert "OpenAI API unavailable" in job["error_message"]
    assert job["diagnostics"]["provider"] == "openai"
    assert job["diagnostics"]["model"] == "gpt-5.4-nano"
    assert job["diagnostics"]["failure"] == "provider_runtime_error"


def test_openai_malformed_provider_result_marks_job_failed(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "PVC pipe")

    run_once(client.app.state.session_factory, ai_provider=MalformedResultProvider())

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "failed"
    assert "malformed" in job["error_message"].lower()
    assert job["diagnostics"]["provider"] == "openai"
    assert job["diagnostics"]["model"] == "gpt-5.4-nano"


def test_openai_provider_success_records_model_and_processor_diagnostics(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "PVC pipe")
    provider = FakeAiProvider([valid_candidate(submission["source_submission"]["id"])])
    provider.provider_name = "openai"
    provider.model = "gpt-5.4-nano"

    run_once(client.app.state.session_factory, ai_provider=provider)

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["processor_name"] == "ai_manual_free_form_v1"
    assert job["diagnostics"]["provider"] == "openai"
    assert job["diagnostics"]["model"] == "gpt-5.4-nano"
    assert "raw_response" not in job["diagnostics"]


def test_processing_once_command_wires_openai_provider_factory(monkeypatch):
    import sys

    import backend.app.processing.__main__ as processing_main

    calls = {}

    class DummyConfig:
        @classmethod
        def from_env(cls):
            calls["config_loaded"] = True
            return "openai-config"

    class DummyProvider:
        def __init__(self, config):
            calls["provider_config"] = config

    def fake_run_once(session_factory, *, ai_provider_factory=None):
        calls["session_factory"] = session_factory
        calls["ai_provider_factory"] = ai_provider_factory
        return 0

    monkeypatch.setattr(sys, "argv", ["processing", "--once"])
    monkeypatch.setattr(processing_main, "database_url_from_env", lambda: "db-url")
    monkeypatch.setattr(processing_main, "create_sqlalchemy_engine", lambda url: "engine")
    monkeypatch.setattr(
        processing_main,
        "sessionmaker",
        lambda bind, expire_on_commit: "session-factory",
    )
    monkeypatch.setattr(processing_main, "run_once", fake_run_once)
    monkeypatch.setattr(processing_main, "OpenAiProviderConfig", DummyConfig, raising=False)
    monkeypatch.setattr(processing_main, "OpenAiExtractionProvider", DummyProvider, raising=False)

    assert processing_main.main() == 0

    provider = calls["ai_provider_factory"]()
    assert calls["session_factory"] == "session-factory"
    assert calls["config_loaded"] is True
    assert isinstance(provider, DummyProvider)
    assert calls["provider_config"] == "openai-config"
