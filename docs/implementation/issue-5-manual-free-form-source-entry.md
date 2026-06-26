# Manual Free-Form Source Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#5`, allowing one free-form Manual Source Entry to preserve typed or pasted source text, create a Source Submission and Processing Job, produce reviewable Extracted Candidates when useful, show `no_candidates_found` when not useful, and use the existing Review Batch lifecycle and import path.

**Architecture:** Introduce the generic Source Submission and Processing Job boundary now. Manual Source Entry becomes the manual-specific content detail for a Source Submission. Processing remains synchronous in issue `#5`, but every manual entry creates a durable Processing Job so later background processing infrastructure in issue `#18` can reuse the same API and data model.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, Postgres, pytest, React/Vite, generated OpenAPI TypeScript client, Vitest/React Testing Library.

---

## Source Context

- Parent PRD: GitHub issue `#1`, `PRD: Habi Per-Project Memory Lab POC`
- Implementation issue: GitHub issue `#5`, `Manual Free-Form Source Entry`
- Blocker complete: GitHub issue `#4`, `Review Batch Lifecycle And Import Gating`
- Follow-up infrastructure issue: GitHub issue `#18`, `Background Processing Infrastructure For Source Processing`
- Glossary: `CONTEXT.md`
- Existing agent guidance: `docs/agents/implementation.md`, `docs/agents/github-branch-pr.md`, `docs/agents/domain.md`
- Relevant existing ADRs: `docs/adr/0003-postgres-with-pgvector-for-poc-storage-and-retrieval.md`, `docs/adr/0005-postgres-backed-processing-jobs-before-redis.md`, `docs/adr/0006-llm-outputs-validated-candidate-proposals.md`, `docs/adr/0012-sqlalchemy-and-alembic-for-persistence.md`, `docs/adr/0015-evidence-links-attach-to-memory-records.md`, `docs/adr/0018-persist-review-batch-status-through-backend-lifecycle-rules.md`
- Issue-specific ADRs: `docs/adr/0039-run-backend-behavior-tests-against-postgres.md` through `docs/adr/0048-review-and-candidates-reference-source-submissions.md`

## Agreed Decisions

- Backend behavior tests should run against Postgres, not SQLite.
- `Source Submission` is the generic project-scoped submitted source input.
- `Manual Source Entry` is the manual-specific typed or pasted evidence detail for a Source Submission.
- `Manual Source Entry.entry_type` supports `structured_row` and `free_form_text`.
- Use one manual source entry endpoint with entry types rather than separate structured and free-form endpoints.
- Source Submissions are immutable evidence events. If manual text or fields need correction, create a new Source Submission.
- Source Submission stores `submitted_at`, `submission_type`, and nullable `entered_by` object metadata. Do not build user/auth behavior yet.
- A manual Source Submission has exactly one Manual Source Entry detail record.
- Every Source Submission has exactly one Processing Job in the POC.
- Processing Job statuses are `queued`, `processing`, `review_ready`, `no_candidates_found`, and `failed`.
- `Source Submission` does not store its own processing status. Derive source processing state from the one Processing Job.
- Processing Job stores `project_workspace_id`, `source_submission_id`, `status`, `source_type`, `processor_name`, `created_at`, `started_at`, `finished_at`, `error_message`, `candidate_count`, and nullable `review_batch_id`.
- Processing Job `candidate_count` counts only candidates actually created for review.
- Processing Job `review_batch_id` is nullable and is set only when processing produces reviewable candidates.
- Free-form Manual Source Entry text is preserved as original entered text. Candidate evidence snippets/locators point back to that text before import.
- Final Evidence Records and Memory Record evidence links are created during import, not during candidate creation.
- The first free-form implementation uses a deterministic parser stub, not an LLM call.
- The parser may produce zero or one candidate in issue `#5`, even though the data model supports zero-or-many candidates.
- The parser considers text useful when it can identify an item or service name plus at least one purchasing detail such as quantity, price, provider, date, or remarks.
- Blank or whitespace-only free-form text is request validation failure, not `no_candidates_found`.
- Free-form text max length is `10,000` characters.
- Useful free-form processing returns normal `201`, with Processing Job status `review_ready`.
- Unusable but non-empty free-form processing returns normal `201`, with Processing Job status `no_candidates_found`.
- `no_candidates_found` creates no Review Batch.
- Review Batch and Extracted Candidate should reference `source_submission_id`, not `manual_source_entry_id`.
- Clean up manual-source-entry ID traces from review/candidate contracts where possible.
- Structured rows also create Source Submission and Processing Job now; structured processing may complete synchronously into `review_ready`.
- Structured rows create one candidate directly from the structured payload.
- Free-form text goes through deterministic parsing before `review_ready` or `no_candidates_found`.
- Issue `#5` completes processing synchronously inside the request. Background worker infrastructure belongs to issue `#18`.
- Add a Processing Job status endpoint now so the frontend and tests use the same seam future polling will use.
- Minimal frontend work is in scope: same manual entry form area with a `Structured Row` / `Free-Form Text` mode switch, a text area, job outcome display, and existing review panel reuse.
- Do not redesign the Upload / Review tab in this issue.
- Do not edit GitHub issue `#5` body; keep decisions in docs and this implementation plan.

## Data Model Changes

### Source Submission

- Add `source_submissions`.
- Fields:
  - `id`
  - `project_workspace_id`
  - `submission_type`, initially `manual_source_entry`
  - `submitted_at`
  - `entered_by`, nullable JSON/object
- Enforce project scoping with foreign keys and indexes.
- Treat rows as immutable after creation.

### Manual Source Entry

- Migrate `manual_source_entries` to reference `source_submission_id` uniquely.
- Fields:
  - `id`
  - `project_workspace_id`
  - `source_submission_id`
  - `entry_type`, `structured_row` or `free_form_text`
  - `structured_payload`, nullable JSON
  - `original_text`, nullable text
- Structured rows store `structured_payload`.
- Free-form entries store `original_text`.
- Keep enough project workspace foreign keys for easy scoping, but source identity should flow through Source Submission.

### Processing Job

- Add `processing_jobs`.
- Fields:
  - `id`
  - `project_workspace_id`
  - `source_submission_id`, unique for the POC
  - `status`
  - `source_type`, initially `manual_source_entry`
  - `processor_name`, for example `structured_manual_row_v1` or `manual_free_form_stub_v1`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `error_message`
  - `candidate_count`
  - `review_batch_id`, nullable
- Add constraints or service-level checks so:
  - `review_ready` has `candidate_count > 0` and `review_batch_id`
  - `no_candidates_found` has `candidate_count = 0` and no review batch
  - `failed` has no review batch

### Review Batch And Extracted Candidate

- Migrate `review_batches.manual_source_entry_id` to `source_submission_id`.
- Migrate `extracted_candidates.manual_source_entry_id` to `source_submission_id`.
- Update schemas and API responses to expose `source_submission_id`, not `manual_source_entry_id`.
- Preserve existing Review Batch status and decision behavior from issue `#4`.

### Evidence

- Update import/evidence promotion to resolve manual source content through Source Submission.
- Evidence Records may still store a manual source entry reference internally if useful, but public review/import contracts should use Source Submission as source identity.
- Candidate pre-import evidence should live in candidate payload/metadata as snippets or locators, not as final Memory Record evidence links.

## Backend API Shape

### Create Manual Source Entry

`POST /api/project-workspaces/{project_workspace_id}/manual-source-entries`

Use one endpoint with an `entry_type`.

Structured row request:

```json
{
  "entry_type": "structured_row",
  "structured_payload": {
    "line_type": "material",
    "name": "PVC pipe",
    "quantity": "20",
    "unit": "pcs",
    "price": "1500",
    "currency": "PHP",
    "provider_name": "ABC Trading",
    "purchase_date": "2025-07-12",
    "remarks_or_terms": "Delivery included"
  }
}
```

Free-form text request:

```json
{
  "entry_type": "free_form_text",
  "original_text": "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
}
```

Response for `review_ready`:

```json
{
  "source_submission": {},
  "manual_source_entry": {},
  "processing_job": {},
  "review_batch": {},
  "candidates": []
}
```

Response for `no_candidates_found`:

```json
{
  "source_submission": {},
  "manual_source_entry": {},
  "processing_job": {
    "status": "no_candidates_found",
    "candidate_count": 0,
    "review_batch_id": null
  },
  "review_batch": null,
  "candidates": []
}
```

### Read Processing Job

`GET /api/project-workspaces/{project_workspace_id}/processing-jobs/{processing_job_id}`

Response should include the full Processing Job read model plus minimal source summary:

```json
{
  "processing_job": {},
  "source_submission": {
    "id": 1,
    "submission_type": "manual_source_entry",
    "submitted_at": "2026-06-27T00:00:00Z"
  },
  "review_batch_id": 1
}
```

The endpoint must enforce selected Project Workspace scoping.

### Review And Import Endpoints

- Keep existing Review Batch read, candidate decision, close-with-no-import, duplicate group, and import endpoints.
- Update contracts to use `source_submission_id`.
- Existing import guards remain backend-owned.
- For imported manual evidence, resolve Source Submission to Manual Source Entry content.

## Deterministic Free-Form Parser Stub

The parser is deliberately modest for issue `#5`.

- Treat the whole text as one candidate opportunity.
- If text is blank or whitespace-only, reject the request with validation error.
- If text has no useful purchasing signal, complete job as `no_candidates_found`.
- A useful candidate requires an item/service name plus at least one purchasing detail.
- Infer `line_type` only from simple cues:
  - service-ish words such as `labor`, `installation`, `hauling`, `coring`, `rental` -> `service`
  - item-ish units such as `pcs`, `bags`, `meters`, `m`, `kg` -> `material`
  - otherwise leave `line_type` null
- Extract provider only from simple cues such as `from ABC Trading`, `by DrillPro`, or `provider: ABC Trading`.
- Leave reviewed category fields blank.
- Optionally include `category_suggestion` metadata when obvious, but do not satisfy import category gates automatically.
- Candidate proposed payload should include purchase-line-like fields plus:
  - `raw_text`
  - `confidence`
  - `category_suggestion`
  - `evidence`

## Suggested File Map

### Backend

- Modify `backend/app/main.py`
  - Import/register processing models and router.
- Modify `backend/app/sources/models.py`
  - Add Source Submission.
  - Change Manual Source Entry to use `source_submission_id`, `entry_type`, `structured_payload`, and `original_text`.
- Modify `backend/app/sources/schemas.py`
  - Add discriminated/manual entry request shape.
  - Add Source Submission read schema.
  - Add unified submission response schema or move it to review/processing schemas if clearer.
- Modify `backend/app/sources/router.py`
  - Create Source Submission.
  - Create Manual Source Entry detail.
  - Create and synchronously complete Processing Job.
  - Return job plus optional review batch and candidates.
- Create `backend/app/processing/models.py`
  - Processing Job persistence.
- Create `backend/app/processing/schemas.py`
  - Processing Job read/detail schemas.
- Create `backend/app/processing/router.py`
  - Processing Job status read endpoint.
- Create `backend/app/processing/manual.py` or similar service module
  - Structured row processing.
  - Deterministic free-form parser stub.
  - Candidate/review batch creation helper.
- Modify `backend/app/review/models.py`
  - Replace manual-source-entry foreign keys with Source Submission foreign keys.
- Modify `backend/app/review/schemas.py`
  - Replace `manual_source_entry_id` with `source_submission_id`.
  - Ensure proposed payload metadata can include raw text, confidence, category suggestion, and evidence.
- Modify `backend/app/review/router.py` and lifecycle/import code
  - Resolve source evidence through Source Submission.
  - Preserve existing issue `#4` lifecycle behavior.
- Modify `backend/app/evidence/models.py` or import code if foreign keys need to point at Source Submission.
- Add Alembic migration under `backend/alembic/versions/`
  - Add Source Submission and Processing Job tables.
  - Migrate manual source entries/review batches/candidates to Source Submission references.
  - Preserve existing local data where practical.
- Modify backend tests under `backend/tests/`
  - Replace SQLite fixtures with Postgres-backed test setup.
  - Update direct model helpers to use Source Submission instead of Manual Source Entry IDs.

### Frontend

- Regenerate `backend/openapi.json`.
- Regenerate `frontend/src/api/generated.ts`.
- Modify `frontend/src/api/client.ts`
  - Add unified manual source entry request support.
  - Add Processing Job status read support.
- Modify `frontend/src/App.tsx`
  - Add `Structured Row` / `Free-Form Text` mode switch.
  - Add free-form text area with validation messaging.
  - Show Processing Job outcome.
  - If `review_ready`, reuse/load existing candidate review panel.
  - If `no_candidates_found`, show no-candidates state and no import action.
- Modify `frontend/src/App.test.tsx`
  - Add/adjust behavior tests for structured and free-form manual entry.
- Modify `frontend/src/styles.css`
  - Keep styling compact and consistent with existing app shell.

## Test-First Sequence

### Task 1: Backend Tests Use Postgres

- [ ] Write or update test fixture expectations so backend tests require `HABI_TEST_DATABASE_URL` or a Postgres test database URL.
- [ ] Watch an existing test fail because it no longer uses SQLite setup.
- [ ] Implement the smallest shared test fixture/conftest change to run backend API tests against Postgres.
- [ ] Ensure tests isolate data by schema reset, migration reset, transaction rollback, or explicit cleanup.

Run:

```powershell
pytest backend/tests/test_project_workspaces_api.py -v
```

### Task 2: Structured Manual Entry Creates Source Submission And Processing Job

- [ ] Write a failing backend API test proving structured manual entry returns Source Submission, Manual Source Entry, Processing Job `review_ready`, Review Batch, and one candidate.
- [ ] Assert Review Batch and Extracted Candidate expose `source_submission_id`.
- [ ] Implement Source Submission and Processing Job tables, schemas, migration, and structured processing path.
- [ ] Keep pending candidates outside active Purchase Lines.

Run:

```powershell
pytest backend/tests/test_manual_source_import_api.py -v
```

### Task 3: Free-Form Manual Entry With Useful Text Creates Reviewable Candidate

- [ ] Write a failing backend API test posting `entry_type = free_form_text` with useful text.
- [ ] Assert original text is preserved.
- [ ] Assert Processing Job ends `review_ready`, `candidate_count = 1`, and has `review_batch_id`.
- [ ] Assert candidate proposed payload includes raw text, proposed fields, confidence, category suggestion, and evidence.
- [ ] Implement deterministic parser stub and free-form processing path.

### Task 4: Free-Form Manual Entry With Unusable Text Produces No Candidates

- [ ] Write a failing backend API test posting non-empty unusable text.
- [ ] Assert response is `201`.
- [ ] Assert Processing Job status is `no_candidates_found`, `candidate_count = 0`, and no Review Batch is created.
- [ ] Assert Review Batch endpoints do not expose empty review work for this submission.
- [ ] Implement no-candidates path.

### Task 5: Free-Form Request Validation

- [ ] Write failing backend API tests for blank/whitespace free-form text and text over `10,000` characters.
- [ ] Assert request validation rejects these before creating Source Submission.
- [ ] Implement schema validation.

### Task 6: Processing Job Status Endpoint

- [ ] Write a failing backend API test for `GET /api/project-workspaces/{project_workspace_id}/processing-jobs/{processing_job_id}`.
- [ ] Assert it returns job detail, minimal Source Submission summary, and nullable Review Batch ID.
- [ ] Assert cross-project access returns 404.
- [ ] Implement endpoint.

### Task 7: Import Uses Source Submission Evidence

- [ ] Write or update failing backend API tests proving approved free-form candidates can be reviewed, imported, and appear in active Purchase Lines with evidence.
- [ ] Assert import resolves manual evidence through Source Submission, not direct `manual_source_entry_id`.
- [ ] Update import/evidence promotion paths.
- [ ] Keep issue `#4` gates passing.

### Task 8: Cleanup Manual Source Entry ID Traces

- [ ] Update schemas, API responses, tests, and helpers to remove `manual_source_entry_id` from Review Batch and Extracted Candidate contracts.
- [ ] Keep Manual Source Entry IDs only where the manual-specific content record is actually being read or returned.
- [ ] Run focused review/import tests.

### Task 9: Frontend Manual Entry Modes

- [ ] Write a failing frontend behavior test for selecting Free-Form Text mode, submitting useful text, seeing Processing Job outcome, seeing the review candidate panel, approving/importing, and seeing an active Purchase Line.
- [ ] Add a test or assertion for `no_candidates_found` showing no candidates and no import action.
- [ ] Implement the minimal UI mode switch and job outcome display.
- [ ] Preserve existing structured-row manual entry behavior.

### Task 10: Contract Regeneration And Final Verification

- [ ] Export OpenAPI after backend changes.
- [ ] Regenerate frontend generated types.
- [ ] Run backend focused tests.
- [ ] Run frontend tests.
- [ ] Run the relevant broader suite if time allows.

Suggested commands:

```powershell
pytest backend/tests -v
cd frontend; npm test -- --run
```

## Testing Decisions

- Use behavior-level tests through backend API endpoints and visible frontend flows.
- Do not test private parser helpers directly unless the parser becomes complex enough to warrant a public module seam. For issue `#5`, prefer API tests.
- Backend tests must run against Postgres.
- TDD is mandatory: one failing test, minimal implementation, repeat.
- The most important trust-boundary tests:
  - Source Submission preserves manual evidence.
  - Processing Job distinguishes `review_ready` from `no_candidates_found`.
  - `no_candidates_found` does not create an empty Review Batch.
  - candidates remain outside active Project Memory before import.
  - approved free-form candidates import through the existing Review Batch lifecycle.
  - project scoping is enforced for Processing Jobs, Review Batches, candidates, and active memory.

## Explicit Deferrals

- Real LLM extraction.
- Background worker loop and async processing: issue `#18`.
- Redis or distributed queue.
- Direct source reprocessing.
- Uploaded file support.
- OCR/table extraction.
- Embeddings and retrieval.
- Multi-candidate deterministic parsing from multiple lines.
- Polished Upload / Review redesign.
- Full evidence inspection UI.
- Auth/user model for `entered_by`.

## Completion Checklist

- [ ] Source Submission glossary/ADR decisions are respected.
- [ ] Backend behavior tests run on Postgres.
- [ ] Source Submission and Processing Job migrations are added.
- [ ] Structured manual entry now creates Source Submission and Processing Job.
- [ ] Free-form manual entry preserves original text.
- [ ] Useful free-form text creates one reviewable Extracted Candidate for the first slice.
- [ ] Unusable non-empty free-form text returns `no_candidates_found`.
- [ ] Blank and overlong free-form text are rejected by validation.
- [ ] Review Batch and Extracted Candidate contracts use `source_submission_id`.
- [ ] Manual-source-entry ID traces are removed from review/candidate contracts where possible.
- [ ] Processing Job status endpoint exists and is project-scoped.
- [ ] Free-form candidates can be reviewed and imported through the existing Review Batch lifecycle.
- [ ] No empty Review Batch is created for no-candidates outcomes.
- [ ] Frontend supports structured/free-form manual entry modes.
- [ ] OpenAPI and generated frontend types are updated.
- [ ] Relevant backend and frontend tests pass.
