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


def test_worker_provider_factory_failure_does_not_claim_queued_job(client):
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

    provider.extract_purchase_lines(original_text="PVC pipe", source_submission_id=123)

    call = client.responses.calls[0]
    assert call["model"] == "gpt-5.4-nano"
    assert "text" in call
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True


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
