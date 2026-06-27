# OpenAI Provider For Free-Form AI Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#25`, adding the real OpenAI API provider for free-form Manual Source Entry AI Extraction while keeping automated tests deterministic.

**Architecture:** Preserve the provider seam from issue `#24`. Add a real OpenAI provider implementation selected by runtime configuration, fail fast before claiming jobs when configuration is missing, request strict structured Purchase Line outputs, and let the already-tested backend validation remain authoritative.

**Tech Stack:** Python OpenAI SDK, OpenAI Responses API, Pydantic, FastAPI settings via environment variables, pytest with mocks/fakes, Postgres worker lifecycle.

---

## Source Context

- Parent issue: `#18`
- Implementation issue: `#25`
- Blocked by: `#24`
- Relevant ADRs: `0078`, `0082`, `0083`, `0084`, `0094`, `0095`, `0108`, `0109`
- Official docs to consult during implementation: OpenAI Responses API and Structured Outputs docs.

## File Map

- Modify `backend/requirements.txt`: add OpenAI SDK if absent.
- Create `backend/app/processing/openai_provider.py`: OpenAI provider implementation and config validation.
- Modify `backend/app/processing/ai_extraction.py`: keep the provider protocol shared by fake and OpenAI providers.
- Modify `backend/app/processing/worker.py`: provider factory and fail-fast config validation before claiming jobs.
- Modify `backend/app/processing/__main__.py`: wire real provider for command execution.
- Add `backend/tests/test_openai_provider.py`: mocked provider tests, no real API call.
- Modify `backend/tests/test_processing_worker.py` or `test_ai_extraction_worker.py`: missing config fail-fast behavior.
- Modify `docs/guides/local-development.md`: environment variables and command examples.

## Runtime Configuration

Required:

```powershell
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="gpt-5.4-nano"
```

Optional:

```powershell
$env:OPENAI_BASE_URL="..."
```

Default model should be `gpt-5.4-nano` when `OPENAI_MODEL` is absent. Missing API key must always fail fast.

## Test Helper Snippets

Add these helpers to `backend/tests/test_openai_provider.py` before the tests that use them:

```python
def create_project(client):
    return client.post("/api/project-workspaces", json={
        "project_name": "Arnaiz Residence Renovation",
        "project_type": "Residential renovation",
        "location": "Makati City",
        "completion_year": 2025,
    }).json()


def create_free_form_submission(client, project_workspace_id: int, text: str):
    return client.post(
        f"/api/project-workspaces/{project_workspace_id}/manual-source-entries",
        json={"entry_type": "free_form_text", "original_text": text},
    ).json()


def get_job(client, project_workspace_id: int, processing_job_id: int):
    return client.get(
        f"/api/project-workspaces/{project_workspace_id}/processing-jobs/{processing_job_id}"
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
```

## Test-First Sequence

### Task 1: Provider Config Validation

**Files:**
- Add: `backend/tests/test_openai_provider.py`
- Create: `backend/app/processing/openai_provider.py`

- [ ] **Step 1: Write failing config test**

```python
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
```

- [ ] **Step 2: Run failing test**

Run: `pytest backend/tests/test_openai_provider.py::test_openai_provider_config_requires_api_key -v`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement config object**

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class OpenAiProviderConfig:
    api_key: str
    model: str = "gpt-5.4-nano"
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> "OpenAiProviderConfig":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for AI Extraction worker")
        return cls(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
```

- [ ] **Step 4: Add positive config test**

```python
def test_openai_provider_config_defaults_model_to_nano(monkeypatch):
    from backend.app.processing.openai_provider import OpenAiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    config = OpenAiProviderConfig.from_env()

    assert config.model == "gpt-5.4-nano"
```

- [ ] **Step 5: Run config tests**

Run: `pytest backend/tests/test_openai_provider.py -k "config" -v`

Expected: PASS.

### Task 2: Worker Fails Fast Before Claiming Without Config

**Files:**
- Modify: `backend/tests/test_openai_provider.py`
- Modify: `backend/app/processing/worker.py`
- Modify: `backend/app/processing/__main__.py`

- [ ] **Step 1: Write failing worker config test**

```python
def test_worker_provider_factory_failure_does_not_claim_queued_job(client, monkeypatch):
    from backend.app.processing.worker import run_once

    project = client.post("/api/project-workspaces", json={
        "project_name": "Arnaiz Residence Renovation",
        "project_type": "Residential renovation",
        "location": "Makati City",
        "completion_year": 2025,
    }).json()
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={"entry_type": "free_form_text", "original_text": "PVC pipe"},
    ).json()

    def failing_factory():
        raise RuntimeError("OPENAI_API_KEY is required")

    try:
        run_once(client.app.state.session_factory, ai_provider_factory=failing_factory)
    except RuntimeError:
        pass

    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/{submission['processing_job']['id']}"
    ).json()["processing_job"]
    assert job["status"] == "queued"
```

- [ ] **Step 2: Run failing test**

Run: `pytest backend/tests/test_openai_provider.py::test_worker_provider_factory_failure_does_not_claim_queued_job -v`

Expected: FAIL if worker claims before config validation.

- [ ] **Step 3: Implement provider factory validation before claim**

In `run_once`, resolve `ai_provider_factory()` before the claim query only when no explicit `ai_provider` was injected and free-form AI provider could be needed. Keep fake provider tests able to inject `ai_provider`.

- [ ] **Step 4: Run test**

Run: `pytest backend/tests/test_openai_provider.py::test_worker_provider_factory_failure_does_not_claim_queued_job -v`

Expected: PASS.

### Task 3: OpenAI Provider Builds Strict Structured Request

**Files:**
- Modify: `backend/tests/test_openai_provider.py`
- Modify: `backend/app/processing/openai_provider.py`

- [ ] **Step 1: Write mocked client test**

```python
class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {
            "output_parsed": {"candidates": []},
            "usage": type("Usage", (), {"input_tokens": 10, "output_tokens": 5})(),
        })()


class FakeOpenAiClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_openai_provider_requests_strict_structured_output():
    from backend.app.processing.openai_provider import OpenAiExtractionProvider, OpenAiProviderConfig

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
```

- [ ] **Step 2: Run failing test**

Run: `pytest backend/tests/test_openai_provider.py::test_openai_provider_requests_strict_structured_output -v`

Expected: FAIL until provider is implemented.

- [ ] **Step 3: Implement provider class**

Use the OpenAI SDK client. Keep schema generation local and explicit:

```python
class OpenAiExtractionProvider:
    provider_name = "openai"

    def __init__(self, config: OpenAiProviderConfig, client=None):
        self.config = config
        self.client = client or OpenAI(api_key=config.api_key, base_url=config.base_url)

    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int) -> dict:
        response = self.client.responses.create(
            model=self.config.model,
            input=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": original_text},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "habi_purchase_line_extraction",
                    "schema": PURCHASE_LINE_EXTRACTION_SCHEMA,
                    "strict": True,
                }
            },
        )
        return response.output_parsed
```

- [ ] **Step 4: Run provider tests**

Run: `pytest backend/tests/test_openai_provider.py -k "structured_output" -v`

Expected: PASS.

### Task 4: Provider Runtime Failures Become Failed Jobs

**Files:**
- Modify: `backend/tests/test_openai_provider.py`
- Modify: `backend/app/processing/worker.py`
- Modify: `backend/app/processing/processors.py`

- [ ] **Step 1: Write failing runtime failure test**

```python
class RuntimeFailingProvider:
    provider_name = "openai"
    model = "gpt-5.4-nano"

    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        raise RuntimeError("OpenAI API unavailable")


def test_openai_runtime_failure_marks_job_failed(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "PVC pipe")

    run_once(client.app.state.session_factory, ai_provider=RuntimeFailingProvider())

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "failed"
    assert "OpenAI API unavailable" in job["error_message"]
```

- [ ] **Step 2: Run failing test**

Run: `pytest backend/tests/test_openai_provider.py::test_openai_runtime_failure_marks_job_failed -v`

Expected: FAIL until worker catches provider exceptions in free-form processing.

- [ ] **Step 3: Implement failure handling**

Catch provider exceptions after job is claimed and marked `processing`; persist:

```python
job.status = "failed"
job.finished_at = utc_now()
job.error_message = str(exc)[:2000]
job.diagnostics = {
    "provider": "openai",
    "model": getattr(provider, "model", None),
    "failure": "provider_runtime_error",
}
```

- [ ] **Step 4: Run test**

Run: `pytest backend/tests/test_openai_provider.py::test_openai_runtime_failure_marks_job_failed -v`

Expected: PASS.

### Task 5: Processor And Model Diagnostics

**Files:**
- Modify: `backend/tests/test_openai_provider.py`
- Modify: `backend/app/processing/openai_provider.py`
- Modify: `backend/app/processing/processors.py`

- [ ] **Step 1: Write diagnostics test**

```python
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
```

- [ ] **Step 2: Implement processor naming**

Queued free-form jobs created by issue `#22` may still use the old processor name. Update submit-time `_processor_name("free_form_text")` to return `ai_manual_free_form_v1` for issue `#25`, or migrate it earlier in issue `#24` if preferred.

- [ ] **Step 3: Run diagnostics tests**

Run: `pytest backend/tests/test_openai_provider.py -k "diagnostics" -v`

Expected: PASS.

### Task 6: Documentation

**Files:**
- Modify: `docs/guides/local-development.md`

- [ ] **Step 1: Add OpenAI worker configuration section**

### AI Extraction Worker

The background worker uses the OpenAI API for free-form Manual Source Entry AI Extraction.

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_MODEL="gpt-5.4-nano"
python -m backend.app.processing --loop
```

Use `--once` when debugging a single queued job:

```powershell
python -m backend.app.processing --once
```

- [ ] **Step 2: Mention tests use fake provider**

Add: "Automated tests do not call the real OpenAI API; they inject fake providers."

### Task 7: Final Verification

- [ ] Run OpenAI provider tests:

`pytest backend/tests/test_openai_provider.py -v`

- [ ] Run AI extraction worker tests:

`pytest backend/tests/test_ai_extraction_worker.py backend/tests/test_processing_worker.py -v`

- [ ] Run frontend tests if generated contracts changed:

`cd frontend; npm test -- --run`

- [ ] Commit:

```powershell
git add backend docs
git commit -m "feat: add openai extraction provider"
```

## Explicit Deferrals

- Real-model e2e quality harness.
- Embeddings and search.
- Model escalation to `gpt-5.4-mini`.
- Raw model response storage.
- Parallel OpenAI calls and rate-limit coordination.
