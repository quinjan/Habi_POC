# Structured Row Jobs Complete Through Background Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#23`, adding a separate background worker command that completes structured-row Manual Source Entry jobs through the Processing Job lifecycle.

**Architecture:** Keep FastAPI responsible for creating queued jobs and move processing into a separate worker command. The worker claims one queued job at a time with Postgres row locking, marks it `processing`, deterministically creates structured-row Review Batch output, and atomically marks the job `review_ready`.

**Tech Stack:** FastAPI, SQLAlchemy, Postgres row locking, pytest, Python module CLI, React/Vite, Vitest/React Testing Library.

---

## Source Context

- Parent issue: `#18`
- Implementation issue: `#23`
- Blocked by: `#22`
- Relevant ADRs: `0076`, `0077`, `0096`, `0104`, `0106`, `0107`

## File Map

- Create `backend/app/processing/worker.py`: job claiming, processing orchestration, run-once and loop modes.
- Create `backend/app/processing/processors.py`: processor selection and structured-row processor.
- Create `backend/app/processing/__main__.py`: command entrypoint, e.g. `python -m backend.app.processing --once`.
- Modify `backend/app/processing/models.py`: ensure diagnostics JSON exists.
- Modify `backend/app/sources/router.py`: keep queued creation from #22.
- Modify `backend/app/sources/models.py`: worker reads Manual Source Entry by Source Submission.
- Modify `backend/app/review/models.py`: worker writes Review Batch and Extracted Candidate.
- Add `backend/tests/test_processing_worker.py`: public-ish worker behavior using DB and job status APIs.
- Modify `frontend/src/App.tsx`: opening review-ready queue entries.
- Modify `frontend/src/App.test.tsx`: ready job opens Review Batch.
- Modify `docs/guides/local-development.md`: run worker command.

## Worker Interfaces

Suggested Python surface:

```python
def run_once(session_factory: sessionmaker) -> int:
    """Process at most one queued job. Return number of jobs processed."""


def run_loop(session_factory: sessionmaker, *, poll_interval_seconds: float = 2.0) -> None:
    """Continuously process queued jobs one at a time."""
```

Job claim query should use one transaction and row locking:

```python
select(ProcessingJob)
.where(ProcessingJob.status == "queued")
.order_by(ProcessingJob.created_at, ProcessingJob.id)
.with_for_update(skip_locked=True)
.limit(1)
```

## Test-First Sequence

### Task 1: Worker Run-Once Claims One Job

**Files:**
- Add: `backend/tests/test_processing_worker.py`
- Create: `backend/app/processing/worker.py`

- [ ] **Step 1: Write failing run-once no-op test**

```python
def test_worker_run_once_returns_zero_when_no_jobs(client):
    from backend.app.processing.worker import run_once

    processed = run_once(client.app.state.session_factory)

    assert processed == 0
```

- [ ] **Step 2: Run the failing test**

Run: `pytest backend/tests/test_processing_worker.py::test_worker_run_once_returns_zero_when_no_jobs -v`

Expected: FAIL because `backend.app.processing.worker` does not exist.

- [ ] **Step 3: Implement minimal worker module**

```python
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.processing.models import ProcessingJob


def run_once(session_factory: sessionmaker) -> int:
    with session_factory() as session:
        job = session.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.status == "queued")
            .order_by(ProcessingJob.created_at, ProcessingJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return 0
        return 0
```

- [ ] **Step 4: Run test**

Run: `pytest backend/tests/test_processing_worker.py::test_worker_run_once_returns_zero_when_no_jobs -v`

Expected: PASS.

### Task 2: Structured Row Job Becomes Review Ready

**Files:**
- Modify: `backend/tests/test_processing_worker.py`
- Modify: `backend/app/processing/worker.py`
- Create: `backend/app/processing/processors.py`

- [ ] **Step 1: Write failing behavior test**

```python
def test_worker_processes_structured_row_job_to_review_ready(client):
    from backend.app.processing.worker import run_once

    project = client.post("/api/project-workspaces", json={
        "project_name": "Arnaiz Residence Renovation",
        "project_type": "Residential renovation",
        "location": "Makati City",
        "completion_year": 2025,
    }).json()
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
        f"/api/project-workspaces/{project['id']}/processing-jobs/{submission['processing_job']['id']}"
    ).json()

    assert job_detail["processing_job"]["status"] == "review_ready"
    assert job_detail["processing_job"]["candidate_count"] == 1
    assert job_detail["review_batch_id"] is not None
    review = client.get(
        f"/api/project-workspaces/{project['id']}/review-batches/{job_detail['review_batch_id']}"
    ).json()
    assert review["candidates"][0]["proposed_payload"]["name"] == "PVC pipe"
```

- [ ] **Step 2: Run failing test**

Run: `pytest backend/tests/test_processing_worker.py::test_worker_processes_structured_row_job_to_review_ready -v`

Expected: FAIL because worker does not process jobs.

- [ ] **Step 3: Implement processor selection and structured processor**

In `processors.py`:

```python
from backend.app.review.models import ExtractedCandidate, ReviewBatch
from backend.app.sources.models import ManualSourceEntry
from backend.app.sources.schemas import StructuredManualSourcePayload


def process_structured_manual_row(session, job):
    manual_entry = session.query(ManualSourceEntry).filter_by(
        source_submission_id=job.source_submission_id,
        project_workspace_id=job.project_workspace_id,
    ).one()
    payload = StructuredManualSourcePayload.model_validate(
        manual_entry.structured_payload
    ).model_dump(mode="json")
    review_batch = ReviewBatch(
        project_workspace_id=job.project_workspace_id,
        source_submission_id=job.source_submission_id,
        status="review_pending",
    )
    session.add(review_batch)
    session.flush()
    candidate = ExtractedCandidate(
        project_workspace_id=job.project_workspace_id,
        review_batch_id=review_batch.id,
        source_submission_id=job.source_submission_id,
        status="pending_review",
        proposed_payload=payload,
    )
    session.add(candidate)
    session.flush()
    return review_batch, [candidate], {"processor": "structured_manual_row_v1"}
```

- [ ] **Step 4: Update worker status transitions**

In `run_once`, after claim:

```python
job.status = "processing"
job.started_at = utc_now()
session.commit()
```

Then process and atomically persist terminal output:

```python
with session_factory() as session:
    with session.begin():
        job = session.get(ProcessingJob, claimed_job_id)
        review_batch, candidates, diagnostics = process_structured_manual_row(session, job)
        job.status = "review_ready"
        job.finished_at = utc_now()
        job.candidate_count = len(candidates)
        job.review_batch_id = review_batch.id
        job.diagnostics = diagnostics
```

- [ ] **Step 5: Run focused tests**

Run: `pytest backend/tests/test_processing_worker.py -v`

Expected: PASS.

### Task 3: Worker CLI Once And Loop Modes

**Files:**
- Modify: `backend/tests/test_processing_worker.py`
- Create: `backend/app/processing/__main__.py`
- Modify: `backend/app/processing/worker.py`

- [ ] **Step 1: Write CLI smoke tests using subprocess**

```python
def test_worker_module_exposes_once_command():
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
```

- [ ] **Step 2: Implement argparse entrypoint**

```python
import argparse

from backend.app.database import create_sqlalchemy_engine, database_url_from_env
from sqlalchemy.orm import sessionmaker

from backend.app.processing.worker import run_loop, run_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    engine = create_sqlalchemy_engine(database_url_from_env())
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    if args.loop:
        run_loop(session_factory)
        return 0
    run_once(session_factory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run CLI test**

Run: `pytest backend/tests/test_processing_worker.py::test_worker_module_exposes_once_command -v`

Expected: PASS.

### Task 4: Project Scoping And Safe Claiming

**Files:**
- Modify: `backend/tests/test_processing_worker.py`
- Modify: `backend/app/processing/worker.py`

- [ ] **Step 1: Write a test proving only one job is processed per run**

```python
def test_worker_run_once_processes_only_one_queued_job(client):
    from backend.app.processing.worker import run_once

    project = client.post("/api/project-workspaces", json={
        "project_name": "Arnaiz Residence Renovation",
        "project_type": "Residential renovation",
        "location": "Makati City",
        "completion_year": 2025,
    }).json()
    for name in ["PVC pipe", "Hauling"]:
        client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "structured_row", "structured_payload": {
                "line_type": "material",
                "name": name,
            }},
        )

    assert run_once(client.app.state.session_factory) == 1
    jobs = client.get(f"/api/project-workspaces/{project['id']}/processing-jobs").json()["items"]

    assert [item["processing_job"]["status"] for item in jobs].count("review_ready") == 1
    assert [item["processing_job"]["status"] for item in jobs].count("queued") == 1
```

- [ ] **Step 2: Run test**

Run: `pytest backend/tests/test_processing_worker.py::test_worker_run_once_processes_only_one_queued_job -v`

Expected: PASS after `run_once` processes exactly one job.

- [ ] **Step 3: Inspect generated SQL or code for row locking**

Confirm the claim query uses `.with_for_update(skip_locked=True)`. Do not replace it with a plain select.

### Task 5: Frontend Opens Ready Structured Job

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write frontend test**

```ts
test("reviewer opens a review-ready structured-row job from the queue", async () => {
  const user = userEvent.setup();

  render(<App />);

  const selector = await screen.findByRole("navigation", {
    name: "Project Workspace selector"
  });
  await user.click(within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" }));

  const queue = await screen.findByRole("region", { name: "Processing Job queue" });
  await user.click(within(queue).getByRole("button", { name: "Open Review Batch" }));

  expect(await screen.findByRole("heading", { name: "Review Candidate" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Implement open action**

For a queue item with `review_batch_id`, call `getReviewBatch(projectId, reviewBatchId)` and set review panel state from the returned `ReviewBatchDetail`.

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend; npm test -- --run App.test.tsx`

Expected: PASS.

### Task 6: Local Development Docs And Verification

- [ ] Add worker command instructions to `docs/guides/local-development.md`:

```powershell
python -m backend.app.processing --once
python -m backend.app.processing --loop
```

- [ ] Run backend tests:

`pytest backend/tests/test_processing_worker.py backend/tests/test_processing_jobs_api.py -v`

- [ ] Run frontend tests:

`cd frontend; npm test -- --run`

- [ ] Commit:

```powershell
git add backend frontend docs
git commit -m "feat: process structured jobs in background worker"
```

## Explicit Deferrals

- Free-form AI Extraction.
- OpenAI provider.
- Parallel worker processing.
- Automatic retries.
- Stale processing job recovery.

