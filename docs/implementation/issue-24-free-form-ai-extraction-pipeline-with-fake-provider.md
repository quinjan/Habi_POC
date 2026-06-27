# Free-Form AI Extraction Pipeline With Fake Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#24`, adding model-independent free-form AI Extraction behind the worker using a fake provider for automated tests.

**Architecture:** Keep the worker lifecycle from issue `#23` and add an AI provider seam for free-form Manual Source Entry processing. The fake provider returns structured extraction results to exercise validation, candidate filtering, no-candidates outcomes, failed outcomes, diagnostics, and frontend queue states without real OpenAI calls.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Postgres, pytest, Python provider protocol, React/Vite, Vitest/React Testing Library.

---

## Source Context

- Parent issue: `#18`
- Implementation issue: `#24`
- Blocked by: `#23`
- Relevant ADRs: `0072`, `0073`, `0079`, `0080`, `0081`, `0082`, `0084`, `0085`, `0086`, `0087`, `0088`, `0089`, `0090`, `0091`, `0092`, `0093`, `0094`, `0095`, `0108`

## File Map

- Create `backend/app/processing/ai_extraction.py`: provider protocol, result models, validation.
- Modify `backend/app/processing/processors.py`: route free-form jobs to AI extraction processor.
- Modify `backend/app/processing/worker.py`: inject provider registry or provider factory for tests.
- Modify `backend/app/processing/schemas.py`: expose Processing Job diagnostics in job detail and list responses.
- Modify `backend/app/processing/models.py`: ensure diagnostics JSON exists.
- Add `backend/tests/test_ai_extraction_worker.py`: fake provider lifecycle tests.
- Modify `frontend/src/App.test.tsx`: free-form queue states and ready review batch behavior.
- Modify `frontend/src/App.tsx`: display failed/no-candidates/review-ready free-form queue entries.

## AI Candidate Payload

Valid Purchase Line candidate payload shape:

```json
{
  "line_type": "material",
  "name": "PVC pipe",
  "quantity": "20",
  "unit": "pcs",
  "price": "1500",
  "currency": "PHP",
  "currency_state": "source_stated",
  "provider_name": "ABC Trading",
  "purchase_date": "2025-07-12",
  "remarks_or_terms": null,
  "confidence": 0.83,
  "category_suggestion": {
    "top_level_category": "Plumbing",
    "subcategory": "Pipes"
  },
  "evidence": {
    "source_submission_id": 1,
    "locator": "manual_source_entry.original_text"
  }
}
```

## Test Helper Snippets

Add these helpers to `backend/tests/test_ai_extraction_worker.py` before the tests that use them:

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
```

## Test-First Sequence

### Task 1: AI Provider Seam

**Files:**
- Add: `backend/app/processing/ai_extraction.py`
- Add: `backend/tests/test_ai_extraction_worker.py`

- [ ] **Step 1: Write failing validation test for one valid candidate**

```python
def test_ai_candidate_validation_accepts_minimal_valid_purchase_line():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[{
            "line_type": "material",
            "name": "PVC pipe",
            "price": "1500",
            "currency": "PHP",
            "currency_state": "source_stated",
            "confidence": 0.8,
            "evidence": {
                "source_submission_id": 10,
                "locator": "manual_source_entry.original_text",
            },
        }],
    )

    assert len(valid) == 1
    assert dropped == 0
```

- [ ] **Step 2: Run failing test**

Run: `pytest backend/tests/test_ai_extraction_worker.py::test_ai_candidate_validation_accepts_minimal_valid_purchase_line -v`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement candidate model and validator**

Use Pydantic models with rules:

```python
class AiPurchaseLineCandidate(BaseModel):
    line_type: Literal["material", "service"]
    name: str = Field(min_length=1, max_length=255)
    quantity: str | None = None
    unit: str | None = None
    price: str | None = None
    currency: str | None = None
    currency_state: Literal["source_stated", "defaulted", "unknown"] = "unknown"
    provider_name: str | None = None
    purchase_date: date | None = None
    remarks_or_terms: str | None = None
    confidence: float = Field(ge=0, le=1)
    category_suggestion: dict | None = None
    evidence: dict
```

Implement `validate_ai_candidates(source_submission_id, raw_candidates) -> tuple[list[dict], int]`.

- [ ] **Step 4: Add tests for invalid candidates**

```python
def test_ai_candidate_validation_drops_invalid_candidates():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[
            {"line_type": "unknown", "name": "PVC pipe", "confidence": 0.8, "evidence": {"source_submission_id": 10}},
            {"line_type": "service", "name": "", "confidence": 0.8, "evidence": {"source_submission_id": 10}},
            {"line_type": "material", "name": "PVC pipe", "confidence": 1.2, "evidence": {"source_submission_id": 10}},
        ],
    )

    assert valid == []
    assert dropped == 3
```

- [ ] **Step 5: Run validation tests**

Run: `pytest backend/tests/test_ai_extraction_worker.py -k "validation" -v`

Expected: PASS.

### Task 2: Free-Form Job With Multiple Valid Candidates

**Files:**
- Modify: `backend/tests/test_ai_extraction_worker.py`
- Modify: `backend/app/processing/worker.py`
- Modify: `backend/app/processing/processors.py`

- [ ] **Step 1: Write fake provider**

In the test file:

```python
class FakeAiProvider:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        self.calls.append((original_text, source_submission_id))
        return {"candidates": self.candidates}
```

- [ ] **Step 2: Write failing worker test**

```python
def test_worker_processes_free_form_ai_candidates_with_fake_provider(client):
    from backend.app.processing.worker import run_once

    project = client.post("/api/project-workspaces", json={
        "project_name": "Arnaiz Residence Renovation",
        "project_type": "Residential renovation",
        "location": "Makati City",
        "completion_year": 2025,
    }).json()
    submission = client.post(
        f"/api/project-workspaces/{project['id']}/manual-source-entries",
        json={"entry_type": "free_form_text", "original_text": "PVC pipe and hauling"},
    ).json()
    provider = FakeAiProvider([
        {"line_type": "material", "name": "PVC pipe", "currency": "PHP", "currency_state": "defaulted", "confidence": 0.8, "evidence": {"source_submission_id": submission["source_submission"]["id"], "locator": "manual_source_entry.original_text"}},
        {"line_type": "service", "name": "Hauling", "currency_state": "unknown", "confidence": 0.7, "evidence": {"source_submission_id": submission["source_submission"]["id"], "locator": "manual_source_entry.original_text"}},
    ])

    assert run_once(client.app.state.session_factory, ai_provider=provider) == 1

    job = client.get(
        f"/api/project-workspaces/{project['id']}/processing-jobs/{submission['processing_job']['id']}"
    ).json()["processing_job"]
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
    ).json()

    assert job["status"] == "review_ready"
    assert job["candidate_count"] == 2
    assert [candidate["proposed_payload"]["name"] for candidate in review["candidates"]] == [
        "PVC pipe",
        "Hauling",
    ]
```

- [ ] **Step 3: Run failing test**

Run: `pytest backend/tests/test_ai_extraction_worker.py::test_worker_processes_free_form_ai_candidates_with_fake_provider -v`

Expected: FAIL because worker has no AI provider route.

- [ ] **Step 4: Implement provider injection**

Update `run_once(session_factory, *, ai_provider=None)` and pass provider into free-form processor. Keep structured-row path unchanged.

- [ ] **Step 5: Run test**

Run: `pytest backend/tests/test_ai_extraction_worker.py::test_worker_processes_free_form_ai_candidates_with_fake_provider -v`

Expected: PASS.

### Task 3: Empty, Mixed, All-Invalid, And Failure Outcomes

**Files:**
- Modify: `backend/tests/test_ai_extraction_worker.py`
- Modify: `backend/app/processing/processors.py`

- [ ] **Step 1: Test empty result**

```python
def test_free_form_ai_empty_result_marks_no_candidates_found(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "Follow up with foreman")
    provider = FakeAiProvider([])

    run_once(client.app.state.session_factory, ai_provider=provider)

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "no_candidates_found"
    assert job["candidate_count"] == 0
    assert job["review_batch_id"] is None
```

- [ ] **Step 2: Test mixed valid and invalid**

```python
def test_free_form_ai_keeps_valid_and_drops_invalid_candidates(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "PVC pipe and unclear thing")
    provider = FakeAiProvider([
        {"line_type": "material", "name": "PVC pipe", "currency_state": "unknown", "confidence": 0.8, "evidence": {"source_submission_id": submission["source_submission"]["id"], "locator": "manual_source_entry.original_text"}},
        {"line_type": "unknown", "name": "Unclear thing", "confidence": 0.5, "evidence": {"source_submission_id": submission["source_submission"]["id"]}},
    ])

    run_once(client.app.state.session_factory, ai_provider=provider)

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "review_ready"
    assert job["candidate_count"] == 1
    assert job["diagnostics"]["dropped_candidate_count"] == 1
```

- [ ] **Step 3: Test all invalid**

```python
def test_free_form_ai_all_invalid_marks_failed(client):
    from backend.app.processing.worker import run_once

    project = create_project(client)
    submission = create_free_form_submission(client, project["id"], "Ambiguous text")
    provider = FakeAiProvider([
        {"line_type": "unknown", "name": "Ambiguous", "confidence": 0.5, "evidence": {"source_submission_id": submission["source_submission"]["id"]}},
    ])

    run_once(client.app.state.session_factory, ai_provider=provider)

    job = get_job(client, project["id"], submission["processing_job"]["id"])
    assert job["status"] == "failed"
    assert "no valid candidate" in job["error_message"].lower()
```

- [ ] **Step 4: Test provider raises**

```python
class RaisingAiProvider:
    def extract_purchase_lines(self, *, original_text: str, source_submission_id: int):
        raise RuntimeError("provider unavailable")
```

Assert job status `failed` and error message contains `provider unavailable`.

- [ ] **Step 5: Implement terminal outcomes**

Use helper functions that persist:

- `review_ready` for valid candidates.
- `no_candidates_found` for successful empty output.
- `failed` for provider exception or all-invalid output.

- [ ] **Step 6: Run AI worker tests**

Run: `pytest backend/tests/test_ai_extraction_worker.py -v`

Expected: PASS.

### Task 4: Currency, Date, Evidence, And Explanation Rules

**Files:**
- Modify: `backend/tests/test_ai_extraction_worker.py`
- Modify: `backend/app/processing/ai_extraction.py`

- [ ] **Step 1: Add focused validation tests**

```python
def test_ai_candidate_defaults_missing_currency_to_php_when_price_exists():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[{
            "line_type": "material",
            "name": "PVC pipe",
            "price": "1500",
            "confidence": 0.8,
            "evidence": {"source_submission_id": 10, "locator": "manual_source_entry.original_text"},
        }],
    )

    assert dropped == 0
    assert valid[0]["currency"] == "PHP"
    assert valid[0]["currency_state"] == "defaulted"
```

```python
def test_ai_candidate_rejects_partial_dates_and_reasoning_fields():
    from backend.app.processing.ai_extraction import validate_ai_candidates

    valid, dropped = validate_ai_candidates(
        source_submission_id=10,
        raw_candidates=[{
            "line_type": "service",
            "name": "Hauling",
            "purchase_date": "2025-07",
            "confidence": 0.8,
            "reasoning": "looks like a hauling service",
            "evidence": {"source_submission_id": 10, "locator": "manual_source_entry.original_text"},
        }],
    )

    assert valid == []
    assert dropped == 1
```

- [ ] **Step 2: Run validation tests**

Run: `pytest backend/tests/test_ai_extraction_worker.py -k "currency or partial_dates" -v`

Expected: FAIL until validation rules are implemented.

- [ ] **Step 3: Implement rules**

Implement:

- default `currency = "PHP"` and `currency_state = "defaulted"` when price exists and currency missing
- preserve explicit uppercase ISO-like currency when source stated
- reject malformed dates
- ignore or reject reasoning fields according to strict candidate model with `extra="forbid"`
- require `evidence.source_submission_id` to equal the job Source Submission ID

- [ ] **Step 4: Run tests**

Run: `pytest backend/tests/test_ai_extraction_worker.py -v`

Expected: PASS.

### Task 5: Frontend Free-Form Queue States

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write tests for queue terminal states**

Add fetch mocks for three free-form jobs:

- `review_ready` with `review_batch_id`
- `no_candidates_found`
- `failed` with `error_message`

Test:

```ts
test("reviewer sees free-form job terminal states in the queue", async () => {
  render(<App />);

  const selector = await screen.findByRole("navigation", {
    name: "Project Workspace selector"
  });
  await userEvent.click(within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" }));

  const queue = await screen.findByRole("region", { name: "Processing Job queue" });
  expect(within(queue).getByText("review_ready")).toBeInTheDocument();
  expect(within(queue).getByText("no_candidates_found")).toBeInTheDocument();
  expect(within(queue).getByText("failed")).toBeInTheDocument();
  expect(within(queue).getByText("provider unavailable")).toBeInTheDocument();
});
```

- [ ] **Step 2: Implement display**

Show valid statuses and error message summaries in the queue. Keep invalid/dropped model outputs hidden from reviewer UI.

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend; npm test -- --run App.test.tsx`

Expected: PASS.

### Task 6: Final Verification

- [ ] Run backend AI worker tests:

`pytest backend/tests/test_ai_extraction_worker.py backend/tests/test_processing_worker.py -v`

- [ ] Run frontend tests:

`cd frontend; npm test -- --run`

- [ ] Commit:

```powershell
git add backend frontend
git commit -m "feat: add fake-provider free-form ai extraction"
```

## Explicit Deferrals

- Real OpenAI API provider.
- Embeddings and search.
- AI duplicate/merge suggestions.
- Raw model response storage.
- Parallel AI calls.
