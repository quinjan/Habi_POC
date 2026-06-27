# Async Manual Source Entry Submission And Job Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#22`, changing Manual Source Entry submission into an asynchronous job-start workflow with a selected Project Workspace job/review queue.

**Architecture:** Keep source submission durable and quick: the create endpoint validates submitted evidence, persists Source Submission and Manual Source Entry, creates one queued Processing Job, and returns no Review Batch or Extracted Candidate data. Add a project-scoped Processing Job list endpoint and update the frontend to poll it every two seconds while leaving worker completion for later issues.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, Postgres, pytest, React/Vite, generated OpenAPI TypeScript client, Vitest/React Testing Library.

---

## Source Context

- Parent issue: `#18`
- Implementation issue: `#22`
- Blocked by: none
- Glossary: `CONTEXT.md`
- Agent guidance: `docs/agents/implementation.md`, `docs/agents/domain.md`
- Relevant ADRs: `0074`, `0075`, `0096`, `0097`, `0098`, `0099`, `0100`, `0101`, `0102`, `0103`, `0105`

## File Map

- Modify `backend/app/sources/router.py`: stop synchronous processing and create queued Processing Jobs for valid Manual Source Entries.
- Modify `backend/app/review/schemas.py`: introduce `ManualSourceEntryQueuedSubmission` for the immediate async submit response.
- Modify `backend/app/processing/models.py`: add nullable JSON diagnostics field.
- Modify `backend/app/processing/schemas.py`: add diagnostics summary fields and a list response schema.
- Modify `backend/app/processing/router.py`: add project-scoped job list endpoint.
- Add Alembic migration under `backend/alembic/versions/`: add a nullable `diagnostics` JSON column to `processing_jobs`.
- Modify `backend/tests/test_manual_source_import_api.py`: update submission expectations to queued/no candidates.
- Add or modify `backend/tests/test_processing_jobs_api.py`: cover job list and project scope.
- Modify `frontend/src/api/client.ts`: add Processing Job list types and API function.
- Modify `frontend/src/App.tsx`: introduce job/review queue state and polling; remove immediate submit-to-review assumption.
- Modify `frontend/src/App.test.tsx`: cover queue display and multiple outstanding jobs.
- Regenerate `backend/openapi.json` and `frontend/src/api/generated.ts`.

## Data Contract

Manual submit response for issue `#22`:

```json
{
  "source_submission": {},
  "manual_source_entry": {},
  "processing_job": {
    "status": "queued",
    "candidate_count": 0,
    "review_batch_id": null
  }
}
```

Project job list response:

```json
{
  "items": [
    {
      "processing_job": {},
      "source_submission": {
        "id": 1,
        "submission_type": "manual_source_entry",
        "submitted_at": "2026-06-27T00:00:00Z"
      },
      "review_batch_id": null
    }
  ]
}
```

## Test-First Sequence

### Task 1: Async Submit Contract

**Files:**
- Modify: `backend/tests/test_manual_source_import_api.py`
- Modify: `backend/app/sources/router.py`
- Modify: `backend/app/review/schemas.py`

- [ ] **Step 1: Write a failing structured-row async submission test**

```python
def test_structured_manual_source_entry_returns_queued_job_without_review_work(tmp_path):
    with make_client(tmp_path) as client:
        project = client.post("/api/project-workspaces", json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        }).json()

        response = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json=structured_manual_entry_payload(
                line_type="material",
                name="PVC pipe",
                quantity="20",
                unit="pcs",
            ),
        )

    body = response.json()
    assert response.status_code == 201
    assert body["processing_job"]["status"] == "queued"
    assert body["processing_job"]["candidate_count"] == 0
    assert body["processing_job"]["review_batch_id"] is None
    assert "review_batch" not in body
    assert "candidates" not in body
```

- [ ] **Step 2: Run the failing test**

Run: `pytest backend/tests/test_manual_source_import_api.py::test_structured_manual_source_entry_returns_queued_job_without_review_work -v`

Expected: FAIL because the current endpoint returns `review_ready`, `review_batch`, and `candidates`.

- [ ] **Step 3: Implement minimal queued structured-row response**

Change `create_manual_source_entry` so after Source Submission and Manual Source Entry creation it creates:

```python
processing_job = ProcessingJob(
    project_workspace_id=project_workspace.id,
    source_submission_id=source_submission.id,
    status="queued",
    source_type="manual_source_entry",
    processor_name=_processor_name(payload.entry_type),
    candidate_count=0,
    review_batch_id=None,
)
```

Do not call `_proposed_payload_for_manual_entry` in this issue.

- [ ] **Step 4: Add the free-form equivalent failing test**

```python
def test_free_form_manual_source_entry_returns_queued_job_without_review_work(tmp_path):
    with make_client(tmp_path) as client:
        project = client.post("/api/project-workspaces", json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        }).json()

        response = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={
                "entry_type": "free_form_text",
                "original_text": "PVC pipe, 20 pcs, from ABC Trading",
            },
        )

    body = response.json()
    assert response.status_code == 201
    assert body["manual_source_entry"]["original_text"] == "PVC pipe, 20 pcs, from ABC Trading"
    assert body["processing_job"]["status"] == "queued"
    assert "review_batch" not in body
    assert "candidates" not in body
```

- [ ] **Step 5: Run both focused tests**

Run: `pytest backend/tests/test_manual_source_import_api.py -k "queued_job_without_review_work" -v`

Expected: PASS.

### Task 2: Submission Validation Still Rejects Non-Evidence

**Files:**
- Modify: `backend/tests/test_manual_source_import_api.py`
- Modify: `backend/app/sources/schemas.py`

- [ ] **Step 1: Write a failing test proving rejected input creates no rows**

```python
def test_invalid_manual_source_entries_are_rejected_before_job_creation(tmp_path):
    with make_client(tmp_path) as client:
        project = client.post("/api/project-workspaces", json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        }).json()

        blank = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": "   "},
        )
        malformed = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "structured_row", "structured_payload": None},
        )
        accepted = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": "PVC pipe"},
        )

    assert blank.status_code == 422
    assert malformed.status_code == 422
    assert accepted.status_code == 201
    assert accepted.json()["source_submission"]["id"] == 1
```

- [ ] **Step 2: Run the focused test**

Run: `pytest backend/tests/test_manual_source_import_api.py::test_invalid_manual_source_entries_are_rejected_before_job_creation -v`

Expected: PASS or fail only because the response schema changed; keep request validation at schema level.

### Task 3: Project Processing Job List Endpoint

**Files:**
- Add: `backend/tests/test_processing_jobs_api.py`
- Modify: `backend/app/processing/schemas.py`
- Modify: `backend/app/processing/router.py`

- [ ] **Step 1: Write the failing list endpoint test**

```python
def test_processing_job_list_returns_project_jobs_newest_first(tmp_path):
    with make_client(tmp_path) as client:
        project = client.post("/api/project-workspaces", json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        }).json()
        other_project = client.post("/api/project-workspaces", json={
            "project_name": "Ortigas Office Fit-Out",
            "project_type": "Commercial fit-out",
            "location": "Pasig City",
            "completion_year": 2024,
        }).json()

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
    assert all(item["processing_job"]["project_workspace_id"] == project["id"] for item in items)
    assert items[0]["source_submission"]["submission_type"] == "manual_source_entry"
```

- [ ] **Step 2: Run the failing test**

Run: `pytest backend/tests/test_processing_jobs_api.py::test_processing_job_list_returns_project_jobs_newest_first -v`

Expected: FAIL with 404.

- [ ] **Step 3: Add schemas**

Add to `backend/app/processing/schemas.py`:

```python
class ProcessingJobListItem(BaseModel):
    processing_job: ProcessingJobRead
    source_submission: SourceSubmissionSummary
    review_batch_id: int | None


class ProcessingJobList(BaseModel):
    items: list[ProcessingJobListItem]
```

- [ ] **Step 4: Add endpoint**

In `backend/app/processing/router.py`, add `GET ""` or `GET "/{project_workspace_id}/processing-jobs"` matching router prefix, using `order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc()).limit(20)`.

- [ ] **Step 5: Run focused tests**

Run: `pytest backend/tests/test_processing_jobs_api.py -v`

Expected: PASS.

### Task 4: Frontend Queue API Client

**Files:**
- Modify: `backend/scripts/export_openapi.py` output path by running it, not editing it.
- Modify generated: `backend/openapi.json`, `frontend/src/api/generated.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Export and regenerate contracts**

Run: `python backend/scripts/export_openapi.py`

Expected: `backend/openapi.json` changes and includes the project Processing Job list path.

Run: `cd frontend; npm run generate:api`

Expected: `frontend/src/api/generated.ts` changes and includes `ProcessingJobList` and `ProcessingJobListItem`.

- [ ] **Step 2: Add client wrapper**

Add exports similar to:

```ts
export type ProcessingJobList = components["schemas"]["ProcessingJobList"];
export type ProcessingJobListItem = components["schemas"]["ProcessingJobListItem"];

export async function listProcessingJobs(
  projectWorkspaceId: number
): Promise<ProcessingJobList> {
  return request<ProcessingJobList>(
    `/api/project-workspaces/${projectWorkspaceId}/processing-jobs`
  );
}
```

- [ ] **Step 3: Run TypeScript check**

Run: `cd frontend; npm test -- --run`

Expected: existing tests may fail because the UI still assumes immediate candidates; type errors should be fixed before moving on.

### Task 5: Frontend Job/Review Queue

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write a failing frontend queue test**

Add fetch mock support for `GET /api/project-workspaces/1/processing-jobs`, then test:

```ts
test("reviewer submits multiple manual entries and sees them in the job queue", async () => {
  const user = userEvent.setup();

  render(<App />);

  const selector = await screen.findByRole("navigation", {
    name: "Project Workspace selector"
  });
  await user.click(within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" }));

  await user.type(screen.getByLabelText("Item or service name"), "PVC pipe");
  await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

  await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
  await user.type(screen.getByLabelText("Free-form source text"), "Hauling service by ABC Trading");
  await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

  const queue = await screen.findByRole("region", { name: "Processing Job queue" });
  expect(within(queue).getAllByText("queued")).toHaveLength(2);
  expect(screen.queryByRole("heading", { name: "Review Candidate" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the failing frontend test**

Run: `cd frontend; npm test -- --run App.test.tsx`

Expected: FAIL because the queue is not implemented.

- [ ] **Step 3: Implement queue state and polling**

Add state:

```ts
const [processingJobs, setProcessingJobs] = useState<ProcessingJobListItem[]>([]);
```

Add polling effect when a project is selected:

```ts
useEffect(() => {
  if (selectedPurchaseLines === null) {
    setProcessingJobs([]);
    return;
  }

  let isMounted = true;
  const projectId = selectedPurchaseLines.project_workspace.id;

  async function refreshJobs() {
    try {
      const response = await listProcessingJobs(projectId);
      if (isMounted) {
        setProcessingJobs(response.items);
      }
    } catch {
      if (isMounted) {
        setErrorMessage("Processing Jobs could not be loaded.");
      }
    }
  }

  void refreshJobs();
  const intervalId = window.setInterval(() => void refreshJobs(), 2000);
  return () => {
    isMounted = false;
    window.clearInterval(intervalId);
  };
}, [selectedPurchaseLines?.project_workspace.id]);
```

- [ ] **Step 4: Render the queue**

Use a region with accessible name `Processing Job queue`, show status, source type, candidate count, and Review Batch ID when present. Keep the form enabled while jobs are queued.

- [ ] **Step 5: Run frontend tests**

Run: `cd frontend; npm test -- --run App.test.tsx`

Expected: PASS.

### Task 6: Final Verification

- [ ] Run backend focused tests:

`pytest backend/tests/test_manual_source_import_api.py backend/tests/test_processing_jobs_api.py -v`

- [ ] Run frontend tests:

`cd frontend; npm test -- --run`

- [ ] Run OpenAPI export after all backend changes:

`python backend/scripts/export_openapi.py`

- [ ] Commit the issue changes:

```powershell
git add backend frontend
git commit -m "feat: add async manual source job queue"
```

## Explicit Deferrals

- Worker command and job completion.
- Review-ready opening from completed jobs.
- AI Extraction and fake provider.
- OpenAI provider.
- Retry and stale-job recovery.
