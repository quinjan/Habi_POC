# Manual Structured Source To Imported Purchase Line Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#3`, allowing one structured Manual Source Entry to become a reviewed Extracted Candidate, then an imported active Purchase Line in the selected Project Workspace with source evidence.

**Architecture:** Follow the PRD trust boundary: source input creates candidates outside active Project Memory, review creates an approved reviewed payload, and only batch import creates active Memory Records. The first slice is synchronous for structured manual entry, but it introduces the thin review/import, taxonomy, memory-record, and evidence shapes needed by later file and AI extraction slices.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, React/Vite, generated OpenAPI TypeScript client, pytest, Vitest/React Testing Library.

---

## Source Context

- Parent PRD: GitHub issue `#1`, `PRD: Habi Per-Project Memory Lab POC`
- Implementation issue: GitHub issue `#3`, `Manual Structured Source To Imported Purchase Line`
- Blocker already complete: GitHub issue `#2`, `Project Workspace App Shell`
- Glossary: `CONTEXT.md`
- Existing agent guidance: `docs/agents/implementation.md`, `docs/agents/github-branch-pr.md`, `docs/agents/domain.md`
- Relevant ADRs: `docs/adr/0002-relational-source-of-truth-with-hybrid-retrieval.md`, `docs/adr/0006-llm-outputs-validated-candidate-proposals.md`, `docs/adr/0011-modular-monolith-fastapi-backend.md`, `docs/adr/0012-sqlalchemy-and-alembic-for-persistence.md`
- New issue-specific ADRs: `docs/adr/0013-thin-project-scoped-taxonomy-records-for-first-import-slice.md`, `docs/adr/0014-shared-memory-record-backbone-from-first-import-slice.md`, `docs/adr/0015-evidence-links-attach-to-memory-records.md`, `docs/adr/0016-exact-name-entity-reuse-with-new-purchase-lines.md`, `docs/adr/0017-backend-enforced-import-guards.md`

## Agreed Decisions

- Follow the PRD workflow rather than a shortcut: Manual Source Entry -> Review Batch -> Extracted Candidate -> review decision -> batch import -> active Project Memory.
- A structured Manual Source Entry creates one Review Batch and one Extracted Candidate synchronously.
- No Processing Job is required for structured manual entry in issue `#3`.
- The reviewer explicitly selects `Material` or `Service`; do not infer line type with heuristics or LLMs.
- A named provider imports as an external Provider memory record; a blank provider imports as unknown provider and must not create a fake Provider record.
- Manual structured row data is enough source evidence for this slice.
- Category and subcategory are review/edit fields and must resolve to a project-scoped Resolved Category Path before import.
- Provider Role is derived for this slice: Material line -> material supplier; Service line -> service provider; blank provider -> no provider role.
- Remarks or terms become an Evidence Annotation with type `general qualifier` when present.
- `price` means the source-stated line amount, defaulting currency to PHP. Do not calculate unit price yet.
- Use thin project-scoped taxonomy records instead of plain category strings.
- Use a thin shared Memory Record backbone for Material, Service, Provider, and Purchase Line records.
- Evidence links attach to `memory_records`, not to each type-specific table.
- Link the same Manual Source Entry evidence to every Memory Record created or reused from the import when the import relies on that source.
- Reuse active Material, Service, and Provider records by exact normalized name within the same Project Workspace.
- Always create a new Purchase Line for each approved candidate. Do not auto-merge repeated purchase facts.
- Candidate editing is pre-import only in this issue. Post-import edits and value history are deferred.
- API endpoints should be workflow-shaped, not generic CRUD.
- The first UI lives inside the selected Project Workspace Purchase Lines view.
- The pending Extracted Candidate must be visible before import.
- Unknown unit, price, date, and provider are durable Unknown Field States, not UI fallbacks.
- Quantity may be absent without an explicit `quantity_unknown` state in this slice.
- The Purchase Lines list should show a lightweight evidence indicator/source label; full evidence inspection is deferred.
- The backend is the source of truth for import guards even when the frontend validates the same rules.

## Suggested File Map

### Backend

- Modify `backend/app/main.py`
  - Include new routers for manual source entries, review batches, and imported purchase-line reads if split from the current project router.
- Modify `backend/app/projects/schemas.py`
  - Replace `ProjectWorkspacePurchaseLinesView.items: list[object]` with typed Purchase Line row schemas.
- Modify `backend/app/projects/router.py`
  - Keep `GET /api/project-workspaces/{project_workspace_id}/purchase-lines`, but return active imported Purchase Lines scoped by Project Workspace.
- Create `backend/app/sources/models.py`
  - Manual Source Entry persistence.
- Create `backend/app/sources/schemas.py`
  - Manual source entry request/response schemas.
- Create `backend/app/sources/router.py`
  - `POST /api/project-workspaces/{project_workspace_id}/manual-source-entries`.
- Create `backend/app/review/models.py`
  - Review Batch and Extracted Candidate persistence.
- Create `backend/app/review/schemas.py`
  - Review batch, candidate, and candidate decision schemas.
- Create `backend/app/review/router.py`
  - `GET /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}`.
  - `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/candidates/{candidate_id}/decision`.
  - `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/import`.
- Create `backend/app/taxonomy/models.py`
  - Thin project-scoped taxonomy nodes with parent-child path.
- Create `backend/app/memory/models.py`
  - Shared Memory Record backbone and type-specific Material, Service, Provider, Purchase Line tables.
- Create `backend/app/evidence/models.py`
  - Manual-source evidence records, Memory Record evidence links, and Evidence Annotations.
- Create one Alembic migration under `backend/alembic/versions/`
  - Add tables for sources, review, taxonomy, memory, and evidence.
- Add or extend backend tests under `backend/tests/`
  - Keep behavior tests at API level.

### Frontend

- Modify `frontend/src/api/client.ts`
  - Export generated types and functions for manual source submission, review batch read, candidate decision, and batch import.
- Regenerate `frontend/src/api/generated.ts` from `backend/openapi.json`.
- Modify `frontend/src/App.tsx`
  - Add the manual source form, visible candidate review panel, approval/import controls, and non-empty Purchase Lines display inside selected workspace view.
- Modify `frontend/src/App.test.tsx`
  - Add one behavior test for the full visible manual-entry review/import flow.
- Modify `frontend/src/styles.css`
  - Add compact workflow, table, and status styling consistent with the existing app shell.

## Backend API Shape

### Submit Manual Source Entry

`POST /api/project-workspaces/{project_workspace_id}/manual-source-entries`

Request body:

```json
{
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
```

Response body should include the created Manual Source Entry, Review Batch, and Extracted Candidate. The candidate must remain outside active Project Memory.

### Read Review Batch

`GET /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}`

Return the batch, candidates, proposed payloads, review decisions if any, and status.

### Review Candidate

`POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/candidates/{candidate_id}/decision`

Request body:

```json
{
  "decision": "approved",
  "reviewed_payload": {
    "line_type": "material",
    "name": "PVC pipe",
    "top_level_category": "Plumbing",
    "subcategory": "Pipes",
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

The candidate must preserve both proposed values and reviewed values.

### Import Review Batch

`POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/import`

Import reads only approved reviewed payloads. It creates active Memory Records and returns imported Purchase Lines.

### Read Active Purchase Lines

`GET /api/project-workspaces/{project_workspace_id}/purchase-lines`

Return only active imported Purchase Lines scoped to the selected Project Workspace. Pending candidates, rejected candidates, and records from other projects must not appear.

Each row should include at least:

```json
{
  "id": 1,
  "item_or_service_name": "PVC pipe",
  "line_type": "material",
  "provider_name": "ABC Trading",
  "provider_type": "external",
  "provider_role": "material_supplier",
  "quantity": "20",
  "unit": "pcs",
  "unit_state": "known",
  "price": "1500",
  "currency": "PHP",
  "price_state": "known",
  "purchase_date": "2025-07-12",
  "date_state": "known",
  "category_path": "Plumbing / Pipes",
  "has_evidence": true,
  "source_label": "Manual Source Entry"
}
```

## Backend Import Guards

The import endpoint must reject the request when:

- the Review Batch does not belong to the selected Project Workspace
- any candidate in the batch lacks a review action
- no candidate is approved
- an approved candidate lacks source evidence
- an approved candidate lacks top-level category or subcategory
- an approved candidate lacks a `Material` or `Service` line type
- the batch was already imported

The frontend may prevent these states, but backend enforcement is required.

## Data Semantics

- `Unknown Field State` applies to unit, price, date, and provider.
- Missing unit -> `unit_state = "unknown"`.
- Missing price -> `price_state = "unknown"`.
- Missing date -> `date_state = "unknown"`.
- Missing provider -> `provider_type = "unknown"`, `provider_name = null`, no Provider memory record.
- Missing quantity remains nullable without `quantity_unknown` in this slice.
- Currency defaults to PHP when price is present and currency is omitted.
- No calculated unit price in this issue.
- Remarks or terms import as Evidence Annotation type `general qualifier`.

## Test-First Sequence

### Task 1: Pending Candidate Does Not Affect Active Purchase Lines

**Files:**
- Test: `backend/tests/test_manual_source_import_api.py`
- Create: `backend/app/sources/models.py`
- Create: `backend/app/sources/schemas.py`
- Create: `backend/app/sources/router.py`
- Create: `backend/app/review/models.py`
- Create: `backend/app/review/schemas.py`
- Create: `backend/app/review/router.py`
- Modify: `backend/app/main.py`
- Create: one Alembic migration under `backend/alembic/versions/`

- [ ] **Step 1: Write the failing API test**

```python
def test_manual_source_entry_creates_pending_candidate_outside_active_purchase_lines(tmp_path):
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

        submission = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={
                "line_type": "material",
                "name": "PVC pipe",
                "quantity": "20",
                "unit": "pcs",
                "price": "1500",
                "currency": "PHP",
                "provider_name": "ABC Trading",
                "purchase_date": "2025-07-12",
                "remarks_or_terms": "Delivery included",
            },
        )

        purchase_lines = client.get(
            f"/api/project-workspaces/{project['id']}/purchase-lines"
        )

    assert submission.status_code == 201
    assert submission.json()["review_batch"]["status"] == "review_pending"
    assert submission.json()["candidate"]["status"] == "pending_review"
    assert purchase_lines.status_code == 200
    assert purchase_lines.json()["items"] == []
```

- [ ] **Step 2: Run the failing test**

Run: `pytest backend/tests/test_manual_source_import_api.py::test_manual_source_entry_creates_pending_candidate_outside_active_purchase_lines -v`

Expected: fails because manual source entry endpoints and models do not exist yet.

- [ ] **Step 3: Implement the smallest vertical slice**

Create the source, review batch, and candidate records synchronously. Do not create Memory Records or Purchase Lines during this task.

- [ ] **Step 4: Run the test again**

Run: `pytest backend/tests/test_manual_source_import_api.py::test_manual_source_entry_creates_pending_candidate_outside_active_purchase_lines -v`

Expected: passes.

### Task 2: Approved Batch Imports Active Purchase Line With Evidence

**Files:**
- Test: `backend/tests/test_manual_source_import_api.py`
- Modify: `backend/app/review/router.py`
- Modify: `backend/app/review/models.py`
- Modify: `backend/app/review/schemas.py`
- Create: `backend/app/taxonomy/models.py`
- Create: `backend/app/memory/models.py`
- Create: `backend/app/evidence/models.py`
- Modify: `backend/app/projects/schemas.py`
- Modify: `backend/app/projects/router.py`
- Modify: the Alembic migration created in Task 1

- [ ] **Step 1: Write the failing import test**

```python
def test_approved_manual_candidate_imports_active_purchase_line_with_evidence(tmp_path):
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
        submission = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={
                "line_type": "material",
                "name": "PVC pipe",
                "quantity": "20",
                "unit": "pcs",
                "price": "1500",
                "provider_name": "ABC Trading",
                "purchase_date": "2025-07-12",
                "remarks_or_terms": "Delivery included",
            },
        ).json()

        decision = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/candidates/{submission['candidate']['id']}/decision",
            json={
                "decision": "approved",
                "reviewed_payload": {
                    "line_type": "material",
                    "name": "PVC pipe",
                    "top_level_category": "Plumbing",
                    "subcategory": "Pipes",
                    "quantity": "20",
                    "unit": "pcs",
                    "price": "1500",
                    "currency": "PHP",
                    "provider_name": "ABC Trading",
                    "purchase_date": "2025-07-12",
                    "remarks_or_terms": "Delivery included",
                },
            },
        )
        imported = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )
        purchase_lines = client.get(
            f"/api/project-workspaces/{project['id']}/purchase-lines"
        )

    assert decision.status_code == 200
    assert imported.status_code == 200
    assert purchase_lines.json()["items"] == [
        {
            "id": imported.json()["imported_purchase_lines"][0]["id"],
            "item_or_service_name": "PVC pipe",
            "line_type": "material",
            "provider_name": "ABC Trading",
            "provider_type": "external",
            "provider_role": "material_supplier",
            "quantity": "20",
            "unit": "pcs",
            "unit_state": "known",
            "price": "1500",
            "currency": "PHP",
            "price_state": "known",
            "purchase_date": "2025-07-12",
            "date_state": "known",
            "category_path": "Plumbing / Pipes",
            "has_evidence": True,
            "source_label": "Manual Source Entry",
        }
    ]
```

- [ ] **Step 2: Run the failing test**

Run: `pytest backend/tests/test_manual_source_import_api.py::test_approved_manual_candidate_imports_active_purchase_line_with_evidence -v`

Expected: fails because import behavior does not exist yet.

- [ ] **Step 3: Implement import**

Create or reuse taxonomy nodes, entity Memory Records, evidence links, annotation, Provider, and new Purchase Line. Make import a batch-level action.

- [ ] **Step 4: Run the test again**

Run: `pytest backend/tests/test_manual_source_import_api.py::test_approved_manual_candidate_imports_active_purchase_line_with_evidence -v`

Expected: passes.

### Task 3: Unknown States And Project Isolation

**Files:**
- Test: `backend/tests/test_manual_source_import_api.py`

- [ ] **Step 1: Write failing tests for unknown states and project scoping**

Cover a manual entry with blank unit, price, date, and provider. After approval/import, assert the Purchase Line shows `unit_state = "unknown"`, `price_state = "unknown"`, `date_state = "unknown"`, and `provider_type = "unknown"`. Also create a second Project Workspace and assert the imported Purchase Line only appears in the original project.

- [ ] **Step 2: Run the tests**

Run: `pytest backend/tests/test_manual_source_import_api.py -v`

Expected: new tests fail before implementation.

- [ ] **Step 3: Implement missing state/scoping behavior**

Infer Unknown Field States in backend import code. Ensure all queries and imports use Project Workspace scoping and foreign-key relationships.

- [ ] **Step 4: Run backend tests**

Run: `pytest backend/tests/test_manual_source_import_api.py backend/tests/test_project_workspaces_api.py -v`

Expected: passes.

### Task 4: Backend Import Guards

**Files:**
- Test: `backend/tests/test_manual_source_import_guards_api.py`

- [ ] **Step 1: Write failing guard tests**

Cover import rejection for missing review decision, missing category path, no approved candidates, wrong Project Workspace, and duplicate import.

- [ ] **Step 2: Run guard tests**

Run: `pytest backend/tests/test_manual_source_import_guards_api.py -v`

Expected: failures for missing guard behavior.

- [ ] **Step 3: Implement guard behavior**

Return `400` or `409` with clear `detail` messages for invalid import attempts. Use `404` when the selected Project Workspace does not own the batch or candidate.

- [ ] **Step 4: Run backend tests**

Run: `pytest backend/tests -v`

Expected: passes.

### Task 5: Frontend Manual Entry Review Import Flow

**Files:**
- Test: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `frontend/src/styles.css`, `frontend/src/api/generated.ts`

- [ ] **Step 1: Export OpenAPI and regenerate frontend types**

Run: `python backend/scripts/export_openapi.py`

Run: `npm run generate:api` from `frontend/`

- [ ] **Step 2: Write failing React behavior test**

Extend the fetch mock to support manual source submission, candidate review, batch import, and purchase-line refresh. The test should select a Project Workspace, submit one Manual Source Entry, see the Review Candidate panel, approve/edit, import, and see the active Purchase Line row.

- [ ] **Step 3: Run the failing frontend test**

Run: `npm test -- --run App.test.tsx` from `frontend/`

Expected: fails because UI controls do not exist yet.

- [ ] **Step 4: Implement the UI**

Add a compact Manual Source Entry form and candidate review/import panel inside the selected Project Workspace Purchase Lines view. Keep the Purchase Lines row unchanged until import succeeds.

- [ ] **Step 5: Run frontend tests**

Run: `npm test -- --run App.test.tsx` from `frontend/`

Expected: passes.

## Explicit Deferrals

- File upload, OCR, table parsing, and async Processing Jobs.
- LLM extraction, confidence, duplicate suggestions, and merge suggestions.
- Full Upload / Review tab with batch lists and pause/resume navigation.
- Taxonomy gates, taxonomy rename UI, taxonomy aliases, and cross-project taxonomy learning.
- Post-import edits, value history, archive behavior, and purchase-line detail view.
- Full evidence inspection UI and search/retrieval behavior.
- Internal provider and supply-and-install provider role selection.
- Calculated unit price suggestions.

## Completion Checklist

- [ ] Backend tests prove pending candidates do not appear in active Project Memory.
- [ ] Backend tests prove import creates active Purchase Line only after review approval.
- [ ] Backend tests prove imported records remain scoped to the selected Project Workspace.
- [ ] Backend tests prove import guards are enforced server-side.
- [ ] Frontend test proves the reviewer can complete the visible manual-entry review/import flow.
- [ ] OpenAPI contract is regenerated and frontend client types are updated.
- [ ] Relevant backend and frontend test suites pass.
- [ ] No direct active-memory creation endpoint is introduced.
