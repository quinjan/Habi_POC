# Multi-Candidate Review Batch UI And Batch Draft Save Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue #31 so reviewers can manage all Extracted Candidates in a Review Batch through a dedicated page, save included/excluded draft decisions in one API call, and import the included set.

**Architecture:** Add backend workflow endpoints for batch draft save and review-time taxonomy mapping, then refactor the React app into a tabbed Project Workspace surface with a dedicated Review Batch page. Keep backend domain language as Approved Candidate / Rejected Candidate / Taxonomy Decision; use checkbox inclusion only as frontend draft UI state.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Postgres behavior tests with `pytest`, React/Vite/TypeScript, Vitest + Testing Library, generated OpenAPI TypeScript client.

---

## Required Context

- Product context: GitHub issue #1 and GitHub issue #31.
- Duplicate UI context: GitHub issue #16 remains out of scope.
- Domain vocabulary: `CONTEXT.md`.
- Relevant ADRs:
  - `docs/adr/0035-candidate-decisions-remain-editable-until-terminal-batch-status.md`
  - `docs/adr/0064-manual-category-paths-can-create-taxonomy-nodes-without-taxonomy-decisions.md`
  - `docs/adr/0065-manual-category-paths-do-not-create-suggestion-mappings.md`
  - `docs/adr/0099-frontend-uses-job-review-queue.md`
  - `docs/adr/0100-job-review-queue-shows-active-and-recent-jobs.md`
- Implementation discipline: use `tdd`; write one failing behavior-level test before each implementation slice.
- Backend test command pattern:

```powershell
$vars = @{}
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { $vars[$matches[1]] = $matches[2] } }
$password = $vars['POSTGRES_PASSWORD']
$env:HABI_TEST_DATABASE_URL = "postgresql+psycopg://habi:$password@localhost:5432/habi_test"
$env:PYTHONPATH='.'
.\.venv\Scripts\pytest.exe backend/tests/test_review_batch_draft_api.py -q
```

- Frontend test command pattern:

```powershell
npm test -- src/App.test.tsx
```

## File Structure

Create:

- `docs/adr/0110-review-batch-uses-taxonomy-defaults-and-batch-draft-save.md`: records the issue #31 review-time taxonomy and draft-save decision.
- `backend/tests/test_review_batch_draft_api.py`: backend behavior tests for batch draft save.
- `backend/tests/test_review_batch_taxonomy_mapping_api.py`: backend behavior tests for immediate taxonomy mapping and apply-to-similar.

Modify:

- `backend/app/review/schemas.py`: add request schemas for batch draft save and review-time taxonomy mapping.
- `backend/app/review/lifecycle.py`: add reusable batch-draft validation helpers used by the router endpoint.
- `backend/app/review/router.py`: add workflow endpoints and small helpers for reviewed payload construction and taxonomy mapping updates.
- `backend/app/processing/ai_extraction.py`: require complete two-level category suggestions for visible AI candidates.
- `backend/tests/test_ai_extraction_worker.py`: update AI validation/worker expectations for complete taxonomy.
- `backend/tests/manual_submission_helpers.py`: leave unchanged unless duplicate candidate helper extraction becomes useful after the first backend test passes.
- `backend/scripts/export_openapi.py`: no code change expected, but run it after backend schema changes.
- `backend/openapi.json`: regenerated contract.
- `frontend/src/api/generated.ts`: regenerated OpenAPI types.
- `frontend/src/api/client.ts`: add `saveReviewBatchDraft` and `saveReviewBatchTaxonomyMapping`.
- `frontend/src/App.tsx`: refactor selected Project Workspace content into Purchase Lines tab, Upload / Review tab, and Review Batch page.
- `frontend/src/App.test.tsx`: replace single-candidate review behavior tests with multi-candidate review/page/draft-save tests.

Do not create duplicate-group UI in this issue. If duplicate conflicts are returned by backend, show a simple conflict message near Import.

---

### Task 1: Record The Review-Time Taxonomy And Batch Draft Decision

**Files:**
- Create: `docs/adr/0110-review-batch-uses-taxonomy-defaults-and-batch-draft-save.md`

- [ ] **Step 1: Add the ADR**

Use `apply_patch` to create:

```md
# Review Batch Uses Taxonomy Defaults And Batch Draft Save

The multi-candidate Review Batch flow treats complete AI-suggested two-level taxonomy as the default reviewed category for visible Extracted Candidates, instead of requiring a separate review-time Approve Taxonomy action. Reviewer changes to that default are saved immediately as mapped Taxonomy Decisions that update affected candidate reviewed category fields, while include/exclude choices remain local batch draft state until Save or Import persists them in one workflow call.
```

- [ ] **Step 2: Verify docs-only diff**

Run:

```powershell
git diff -- docs/adr/0110-review-batch-uses-taxonomy-defaults-and-batch-draft-save.md
```

Expected: the ADR file exists and contains the paragraph above.

- [ ] **Step 3: Commit**

```powershell
git add docs/adr/0110-review-batch-uses-taxonomy-defaults-and-batch-draft-save.md
git commit -m "docs: record review batch taxonomy defaults decision"
```

---

### Task 2: Add Batch Draft Save Backend API

**Files:**
- Create: `backend/tests/test_review_batch_draft_api.py`
- Modify: `backend/app/review/schemas.py`
- Modify: `backend/app/review/router.py`
- Modify: `backend/app/review/lifecycle.py`

- [ ] **Step 1: Write failing test for saving included/excluded candidates in one request**

Create `backend/tests/test_review_batch_draft_api.py`:

```python
from fastapi.testclient import TestClient

from backend.tests.db import make_postgres_test_client
from backend.tests.manual_submission_helpers import create_review_ready_manual_submission


def make_client(_tmp_path):
    return make_postgres_test_client()


def test_review_batch_draft_saves_included_and_excluded_candidates(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "service",
                "name": "Hauling",
                "quantity": "1",
                "unit": "lot",
                "price": "8000",
                "provider_name": "JRS Hauling",
                "category_suggestion": {
                    "top_level_category": "Services",
                    "subcategory": "Hauling",
                },
            },
        )

        response = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": submission["candidates"][0]["id"],
                        "included": True,
                        "reviewed_payload": {
                            "line_type": "material",
                            "name": "PVC pipe",
                            "top_level_category": "Plumbing",
                            "subcategory": "Pipes",
                            "quantity": "20",
                            "unit": "pcs",
                            "price": "1500",
                            "provider_name": "ABC Trading",
                        },
                    },
                    {
                        "candidate_id": second_candidate_id,
                        "included": False,
                        "reviewed_payload": None,
                    },
                ]
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["review_batch"]["status"] == "ready_to_import"
    candidates = {candidate["id"]: candidate for candidate in body["candidates"]}
    assert candidates[submission["candidates"][0]["id"]]["decision"] == "approved"
    assert candidates[submission["candidates"][0]["id"]]["status"] == "approved_for_import"
    assert candidates[submission["candidates"][0]["id"]]["reviewed_payload"]["subcategory"] == "Pipes"
    assert candidates[second_candidate_id]["decision"] == "rejected"
    assert candidates[second_candidate_id]["status"] == "rejected_for_import"
    assert candidates[second_candidate_id]["reviewed_payload"] is None


def create_manual_submission(client: TestClient):
    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={
            "line_type": "material",
            "name": "PVC pipe",
            "quantity": "20",
            "unit": "pcs",
            "price": "1500",
            "provider_name": "ABC Trading",
            "category_suggestion": {
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
            },
        },
    )
    return project, submission


def add_candidate_to_batch(
    client: TestClient,
    *,
    project_workspace_id: int,
    review_batch_id: int,
    source_submission_id: int,
    proposed_payload: dict,
) -> int:
    from backend.app.review.models import ExtractedCandidate

    with client.app.state.session_factory() as session:
        candidate = ExtractedCandidate(
            project_workspace_id=project_workspace_id,
            review_batch_id=review_batch_id,
            source_submission_id=source_submission_id,
            status="pending_review",
            proposed_payload=proposed_payload,
        )
        session.add(candidate)
        session.commit()
        return candidate.id
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$vars = @{}
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { $vars[$matches[1]] = $matches[2] } }
$password = $vars['POSTGRES_PASSWORD']
$env:HABI_TEST_DATABASE_URL = "postgresql+psycopg://habi:$password@localhost:5432/habi_test"
$env:PYTHONPATH='.'
.\.venv\Scripts\pytest.exe backend/tests/test_review_batch_draft_api.py::test_review_batch_draft_saves_included_and_excluded_candidates -q
```

Expected: FAIL with `405 Method Not Allowed` or `404 Not Found` for `/review-draft`.

- [ ] **Step 3: Add schemas**

In `backend/app/review/schemas.py`, add after `CandidateDecisionRequest`:

```python
class ReviewBatchDraftCandidate(BaseModel):
    candidate_id: int
    included: bool
    reviewed_payload: ReviewedPurchaseLinePayload | None = None


class ReviewBatchDraftSaveRequest(BaseModel):
    candidates: list[ReviewBatchDraftCandidate] = Field(min_length=1)
```

Add `ReviewBatchDraftSaveRequest` to the router import list in `backend/app/review/router.py`.

- [ ] **Step 4: Add lifecycle validation helper**

In `backend/app/review/lifecycle.py`, add:

```python
def validate_approved_reviewed_payload(reviewed_payload: dict | None) -> None:
    if reviewed_payload is None:
        raise ValueError("Included candidates require reviewed payloads")

    payload = ReviewedPurchaseLinePayload.model_validate(reviewed_payload)
    if payload.line_type not in {"material", "service"}:
        raise ValueError("Included candidates require a Material or Service line type")
    if not _present(payload.name):
        raise ValueError("Included candidates require an item or service name")
    if not _present(payload.top_level_category) or not _present(payload.subcategory):
        raise ValueError("Included candidates require a resolved category path")
```

- [ ] **Step 5: Add endpoint**

In `backend/app/review/router.py`, import `validate_approved_reviewed_payload` from lifecycle. Add below `decide_candidate`:

```python
@router.put(
    "/{project_workspace_id}/review-batches/{review_batch_id}/review-draft",
    response_model=ReviewBatchDetail,
)
def save_review_batch_draft(
    project_workspace_id: int,
    review_batch_id: int,
    payload: ReviewBatchDraftSaveRequest,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    candidates_by_id = {
        candidate.id: candidate
        for candidate in _get_batch_candidates(session, review_batch.id)
    }
    requested_ids = [item.candidate_id for item in payload.candidates]
    if len(set(requested_ids)) != len(requested_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review draft cannot contain duplicate candidates",
        )
    if set(requested_ids) != set(candidates_by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review draft must include every candidate in the Review Batch",
        )

    try:
        for item in payload.candidates:
            reviewed_payload = (
                item.reviewed_payload.model_dump(mode="json")
                if item.reviewed_payload is not None
                else None
            )
            if item.included:
                validate_approved_reviewed_payload(reviewed_payload)
                apply_candidate_decision(
                    session=session,
                    review_batch=review_batch,
                    candidate=candidates_by_id[item.candidate_id],
                    decision="approved",
                    reviewed_payload=reviewed_payload,
                )
            else:
                apply_candidate_decision(
                    session=session,
                    review_batch=review_batch,
                    candidate=candidates_by_id[item.candidate_id],
                    decision="rejected",
                    reviewed_payload=None,
                )
    except TerminalReviewBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)
```

- [ ] **Step 6: Run test and verify it passes**

Run the same test command from Step 2.

Expected: PASS.

- [ ] **Step 7: Add atomic validation tests**

Append to `backend/tests/test_review_batch_draft_api.py`:

```python
def test_review_batch_draft_rejects_included_candidate_without_category_path(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)

        response = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": submission["candidates"][0]["id"],
                        "included": True,
                        "reviewed_payload": {
                            "line_type": "material",
                            "name": "PVC pipe",
                            "top_level_category": "Plumbing",
                            "quantity": "20",
                        },
                    }
                ]
            },
        )
        batch = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}"
        ).json()

    assert response.status_code == 400
    assert response.json()["detail"] == "Included candidates require a resolved category path"
    assert batch["candidates"][0]["decision"] is None
    assert batch["review_batch"]["status"] == "review_pending"


def test_review_batch_draft_rejects_missing_candidate_from_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={"line_type": "material", "name": "PVC elbow"},
        )

        response = client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": submission["candidates"][0]["id"],
                        "included": False,
                        "reviewed_payload": None,
                    }
                ]
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Review draft must include every candidate in the Review Batch"
```

- [ ] **Step 8: Run draft API tests**

Run:

```powershell
.\.venv\Scripts\pytest.exe backend/tests/test_review_batch_draft_api.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add backend/app/review/schemas.py backend/app/review/router.py backend/app/review/lifecycle.py backend/tests/test_review_batch_draft_api.py
git commit -m "feat: save review batch draft decisions"
```

---

### Task 3: Add Review-Time Taxonomy Mapping API

**Files:**
- Create: `backend/tests/test_review_batch_taxonomy_mapping_api.py`
- Modify: `backend/app/review/schemas.py`
- Modify: `backend/app/review/router.py`

- [ ] **Step 1: Write failing test for exact normalized apply-to-similar mapping**

Create `backend/tests/test_review_batch_taxonomy_mapping_api.py`:

```python
from fastapi.testclient import TestClient

from backend.tests.db import make_postgres_test_client
from backend.tests.manual_submission_helpers import create_review_ready_manual_submission


def make_client(_tmp_path):
    return make_postgres_test_client()


def test_review_taxonomy_mapping_updates_all_matching_candidates_in_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        first_candidate_id = submission["candidates"][0]["id"]
        second_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "material",
                "name": "PVC elbow",
                "quantity": "10",
                "unit": "pcs",
                "category_suggestion": {
                    "top_level_category": " mechanical ",
                    "subcategory": "PIPE   MATERIALS",
                },
            },
        )
        unrelated_candidate_id = add_candidate_to_batch(
            client,
            project_workspace_id=project["id"],
            review_batch_id=submission["review_batch"]["id"],
            source_submission_id=submission["source_submission"]["id"],
            proposed_payload={
                "line_type": "service",
                "name": "Hauling",
                "category_suggestion": {
                    "top_level_category": "Services",
                    "subcategory": "Hauling",
                },
            },
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-mappings",
            json={
                "candidate_id": first_candidate_id,
                "top_level_category": "Plumbing",
                "subcategory": "Pipes",
                "apply_to_similar": True,
            },
        )

    assert response.status_code == 200
    candidates = {candidate["id"]: candidate for candidate in response.json()["candidates"]}
    assert candidates[first_candidate_id]["reviewed_payload"]["top_level_category"] == "Plumbing"
    assert candidates[first_candidate_id]["reviewed_payload"]["subcategory"] == "Pipes"
    assert candidates[second_candidate_id]["reviewed_payload"]["top_level_category"] == "Plumbing"
    assert candidates[second_candidate_id]["reviewed_payload"]["subcategory"] == "Pipes"
    assert candidates[unrelated_candidate_id]["reviewed_payload"] is None
    decisions = response.json()["taxonomy_decisions"]
    assert decisions[-1]["decision"] == "mapped"
    assert decisions[-1]["suggested_top_level_category"] == "Mechanical"
    assert decisions[-1]["suggested_subcategory"] == "Pipe Materials"


def create_manual_submission(client: TestClient):
    project = client.post(
        "/api/project-workspaces",
        json={
            "project_name": "Arnaiz Residence Renovation",
            "project_type": "Residential renovation",
            "location": "Makati City",
            "completion_year": 2025,
        },
    ).json()
    submission = create_review_ready_manual_submission(
        client,
        project_workspace_id=project["id"],
        structured_payload={
            "line_type": "material",
            "name": "PVC pipe",
            "quantity": "20",
            "unit": "pcs",
            "category_suggestion": {
                "top_level_category": "Mechanical",
                "subcategory": "Pipe Materials",
            },
        },
    )
    return project, submission


def add_candidate_to_batch(
    client: TestClient,
    *,
    project_workspace_id: int,
    review_batch_id: int,
    source_submission_id: int,
    proposed_payload: dict,
) -> int:
    from backend.app.review.models import ExtractedCandidate

    with client.app.state.session_factory() as session:
        candidate = ExtractedCandidate(
            project_workspace_id=project_workspace_id,
            review_batch_id=review_batch_id,
            source_submission_id=source_submission_id,
            status="pending_review",
            proposed_payload=proposed_payload,
        )
        session.add(candidate)
        session.commit()
        return candidate.id
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\pytest.exe backend/tests/test_review_batch_taxonomy_mapping_api.py::test_review_taxonomy_mapping_updates_all_matching_candidates_in_batch -q
```

Expected: FAIL with `404 Not Found` or `405 Method Not Allowed`.

- [ ] **Step 3: Add schema**

In `backend/app/review/schemas.py`, add after `TaxonomyDecisionCreate`:

```python
class ReviewBatchTaxonomyMappingRequest(BaseModel):
    candidate_id: int
    top_level_category: str = Field(min_length=1, max_length=255)
    subcategory: str = Field(min_length=1, max_length=255)
    apply_to_similar: bool = False
```

Import `ReviewBatchTaxonomyMappingRequest` in `backend/app/review/router.py`.

- [ ] **Step 4: Add endpoint**

In `backend/app/review/router.py`, add below `create_taxonomy_decision`:

```python
@router.post(
    "/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-mappings",
    response_model=ReviewBatchDetail,
)
def save_review_batch_taxonomy_mapping(
    project_workspace_id: int,
    review_batch_id: int,
    payload: ReviewBatchTaxonomyMappingRequest,
    session: Session = Depends(get_session),
) -> ReviewBatchDetail:
    review_batch = _get_project_review_batch(session, project_workspace_id, review_batch_id)
    _ensure_review_batch_editable_or_conflict(review_batch)
    target_candidate = session.scalar(
        select(ExtractedCandidate).where(
            ExtractedCandidate.id == payload.candidate_id,
            ExtractedCandidate.review_batch_id == review_batch.id,
            ExtractedCandidate.project_workspace_id == project_workspace_id,
        )
    )
    if target_candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    suggestion = _candidate_taxonomy_suggestion(target_candidate)
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate has no complete AI taxonomy suggestion",
        )

    resolved_leaf = _approve_taxonomy_path(
        session=session,
        project_workspace_id=project_workspace_id,
        top_level_category=payload.top_level_category,
        subcategory=payload.subcategory,
    )
    taxonomy_decision = TaxonomyDecision(
        project_workspace_id=project_workspace_id,
        review_batch_id=review_batch.id,
        suggested_top_level_category=suggestion["top_level_category"],
        suggested_subcategory=suggestion["subcategory"],
        normalized_suggested_path_key=normalized_taxonomy_path_key(
            suggestion["top_level_category"],
            suggestion["subcategory"],
        ),
        decision="mapped",
        resolved_taxonomy_node_id=resolved_leaf.id,
    )
    session.add(taxonomy_decision)

    target_path_key = normalized_taxonomy_path_key(
        suggestion["top_level_category"],
        suggestion["subcategory"],
    )
    candidates_to_update = []
    for candidate in _get_batch_candidates(session, review_batch.id):
        candidate_suggestion = _candidate_taxonomy_suggestion(candidate)
        if candidate_suggestion is None:
            continue
        if not payload.apply_to_similar and candidate.id != target_candidate.id:
            continue
        if payload.apply_to_similar and normalized_taxonomy_path_key(
            candidate_suggestion["top_level_category"],
            candidate_suggestion["subcategory"],
        ) != target_path_key:
            continue
        candidates_to_update.append(candidate)

    for candidate in candidates_to_update:
        candidate.reviewed_payload = _reviewed_payload_with_category(
            candidate=candidate,
            top_level_category=payload.top_level_category,
            subcategory=payload.subcategory,
        )

    recalculate_review_batch_status(session=session, review_batch=review_batch)
    session.commit()
    session.refresh(review_batch)
    return _review_batch_detail(session, review_batch)
```

Add helper functions near `_batch_has_taxonomy_suggestion`:

```python
def _candidate_taxonomy_suggestion(candidate: ExtractedCandidate) -> dict[str, str] | None:
    suggestion = candidate.proposed_payload.get("category_suggestion")
    if not isinstance(suggestion, dict):
        return None
    top_level_category = suggestion.get("top_level_category")
    subcategory = suggestion.get("subcategory")
    if not isinstance(top_level_category, str) or not _present(top_level_category):
        return None
    if not isinstance(subcategory, str) or not _present(subcategory):
        return None
    return {
        "top_level_category": top_level_category.strip(),
        "subcategory": subcategory.strip(),
    }


def _reviewed_payload_with_category(
    *,
    candidate: ExtractedCandidate,
    top_level_category: str,
    subcategory: str,
) -> dict:
    payload = {
        **candidate.proposed_payload,
        **(candidate.reviewed_payload or {}),
        "top_level_category": top_level_category.strip(),
        "subcategory": subcategory.strip(),
    }
    payload.pop("category_suggestion", None)
    payload.pop("confidence", None)
    payload.pop("currency_state", None)
    payload.pop("evidence", None)
    return ReviewedPurchaseLinePayload.model_validate(payload).model_dump(mode="json")
```

- [ ] **Step 5: Run test and verify it passes**

Run the same test command from Step 2.

Expected: PASS.

- [ ] **Step 6: Add terminal batch rejection test**

Append:

```python
def test_review_taxonomy_mapping_rejects_terminal_batch(tmp_path):
    with make_client(tmp_path) as client:
        project, submission = create_manual_submission(client)
        candidate_id = submission["candidates"][0]["id"]
        client.put(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/review-draft",
            json={
                "candidates": [
                    {
                        "candidate_id": candidate_id,
                        "included": True,
                        "reviewed_payload": {
                            "line_type": "material",
                            "name": "PVC pipe",
                            "top_level_category": "Plumbing",
                            "subcategory": "Pipes",
                        },
                    }
                ]
            },
        )
        client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/import"
        )

        response = client.post(
            f"/api/project-workspaces/{project['id']}/review-batches/{submission['review_batch']['id']}/taxonomy-mappings",
            json={
                "candidate_id": candidate_id,
                "top_level_category": "Plumbing",
                "subcategory": "Pipe Materials",
                "apply_to_similar": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Terminal review batches cannot be changed"
```

- [ ] **Step 7: Run mapping tests**

Run:

```powershell
.\.venv\Scripts\pytest.exe backend/tests/test_review_batch_taxonomy_mapping_api.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/review/schemas.py backend/app/review/router.py backend/tests/test_review_batch_taxonomy_mapping_api.py
git commit -m "feat: save review batch taxonomy mappings"
```

---

### Task 4: Require Complete AI Taxonomy For Visible AI Candidates

**Files:**
- Modify: `backend/app/processing/ai_extraction.py`
- Modify: `backend/tests/test_ai_extraction_worker.py`

- [ ] **Step 1: Write failing validation test**

In `backend/tests/test_ai_extraction_worker.py`, update `test_ai_candidate_validation_accepts_minimal_valid_purchase_line` so the raw candidate includes:

```python
"category_suggestion": {
    "top_level_category": "Plumbing",
    "subcategory": "Pipes",
},
```

Then append:

```python
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
```

- [ ] **Step 2: Run validation tests and verify failure**

Run:

```powershell
.\.venv\Scripts\pytest.exe backend/tests/test_ai_extraction_worker.py -k "complete_taxonomy or minimal_valid" -q
```

Expected: new test FAILS because taxonomy is currently optional.

- [ ] **Step 3: Implement complete taxonomy validation**

In `backend/app/processing/ai_extraction.py`, change `AiCategorySuggestion`:

```python
class AiCategorySuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_level_category: str = Field(min_length=1, max_length=255)
    subcategory: str = Field(min_length=1, max_length=255)

    @field_validator("top_level_category", "subcategory", mode="before")
    @classmethod
    def strip_required_taxonomy_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value
```

In `AiPurchaseLineCandidate`, change:

```python
category_suggestion: AiCategorySuggestion
```

- [ ] **Step 4: Update AI worker fake-provider candidates**

In `backend/tests/test_ai_extraction_worker.py`, add complete `category_suggestion` objects to every fake candidate that should remain valid:

```python
"category_suggestion": {
    "top_level_category": "Plumbing",
    "subcategory": "Pipes",
},
```

For service examples, use:

```python
"category_suggestion": {
    "top_level_category": "Services",
    "subcategory": "Hauling",
},
```

- [ ] **Step 5: Run AI extraction tests**

Run:

```powershell
.\.venv\Scripts\pytest.exe backend/tests/test_ai_extraction_worker.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/processing/ai_extraction.py backend/tests/test_ai_extraction_worker.py
git commit -m "feat: require complete taxonomy for AI candidates"
```

---

### Task 5: Regenerate OpenAPI And Frontend Client Methods

**Files:**
- Modify: `backend/openapi.json`
- Modify: `frontend/src/api/generated.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Regenerate backend OpenAPI**

Run:

```powershell
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe backend/scripts/export_openapi.py
```

Expected: `backend/openapi.json` changes and includes `ReviewBatchDraftSaveRequest` and `ReviewBatchTaxonomyMappingRequest`.

- [ ] **Step 2: Regenerate frontend generated types**

Run:

```powershell
cd frontend
npm run generate:api
cd ..
```

Expected: `frontend/src/api/generated.ts` changes.

- [ ] **Step 3: Add client exports and functions**

In `frontend/src/api/client.ts`, add type exports:

```ts
export type ReviewBatchDraftSaveRequest =
  components["schemas"]["ReviewBatchDraftSaveRequest"];
export type ReviewBatchTaxonomyMappingRequest =
  components["schemas"]["ReviewBatchTaxonomyMappingRequest"];
```

Add functions after `getReviewBatch`:

```ts
export async function saveReviewBatchDraft(
  projectWorkspaceId: number,
  reviewBatchId: number,
  payload: ReviewBatchDraftSaveRequest
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/review-draft`,
    {
      method: "PUT",
      body: JSON.stringify(payload)
    }
  );
}

export async function saveReviewBatchTaxonomyMapping(
  projectWorkspaceId: number,
  reviewBatchId: number,
  payload: ReviewBatchTaxonomyMappingRequest
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/taxonomy-mappings`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}
```

- [ ] **Step 4: Run type build**

Run:

```powershell
cd frontend
npm run build
cd ..
```

Expected: TypeScript build passes.

- [ ] **Step 5: Commit**

```powershell
git add backend/openapi.json frontend/src/api/generated.ts frontend/src/api/client.ts
git commit -m "chore: expose review batch draft client"
```

---

### Task 6: Refactor Frontend To Project Tabs And Dedicated Review Batch Page

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing UI test for tabs and dedicated review page**

In `frontend/src/App.test.tsx`, replace the old single-candidate import test with:

```ts
test("reviewer opens Upload Review tab and navigates to a dedicated Review Batch page", async () => {
  const user = userEvent.setup();

  render(<App />);

  const selector = await screen.findByRole("navigation", {
    name: "Project Workspace selector"
  });
  await user.click(
    within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
  );

  expect(await screen.findByRole("tab", { name: "Purchase Lines" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
  expect(window.location.pathname).toBe("/projects/1/upload-review");
  expect(screen.getByRole("heading", { name: "Create Manual Source Entry" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Processing Job queue" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
  await user.type(
    screen.getByLabelText("Free-form source text"),
    "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
  );
  await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
  await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

  expect(window.location.pathname).toBe("/projects/1/review-batches/10");
  expect(await screen.findByRole("heading", { name: "Review Batch #10" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Back to Upload / Review" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Purchase Lines" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx -t "dedicated Review Batch page"
cd ..
```

Expected: FAIL because tabs and dedicated page do not exist.

- [ ] **Step 3: Add route state and tab helpers**

In `frontend/src/App.tsx`, add types near existing type declarations:

```ts
type WorkspaceRoute =
  | { name: "purchase_lines" }
  | { name: "upload_review" }
  | { name: "review_batch"; reviewBatchId: number };
```

Add state:

```ts
const [workspaceRoute, setWorkspaceRoute] = useState<WorkspaceRoute>({ name: "purchase_lines" });
```

Add helper functions inside `App`:

```ts
function navigateWorkspace(projectId: number, route: WorkspaceRoute) {
  setWorkspaceRoute(route);
  const path =
    route.name === "purchase_lines"
      ? `/projects/${projectId}/purchase-lines`
      : route.name === "upload_review"
        ? `/projects/${projectId}/upload-review`
        : `/projects/${projectId}/review-batches/${route.reviewBatchId}`;
  window.history.pushState({}, "", path);
}
```

Change `handleSelectProject` to:

```ts
navigateWorkspace(project.id, { name: "purchase_lines" });
```

Change `handleOpenReviewBatch` after `setActiveReviewBatch(detail)` to:

```ts
navigateWorkspace(selectedPurchaseLines.project_workspace.id, {
  name: "review_batch",
  reviewBatchId
});
```

- [ ] **Step 4: Render tabs and route-specific content**

Inside selected workspace content, add:

```tsx
<div className="workspace-tabs" role="tablist" aria-label="Project Workspace sections">
  <button
    role="tab"
    aria-selected={workspaceRoute.name === "purchase_lines"}
    onClick={() =>
      navigateWorkspace(selectedPurchaseLines.project_workspace.id, { name: "purchase_lines" })
    }
    type="button"
  >
    Purchase Lines
  </button>
  <button
    role="tab"
    aria-selected={workspaceRoute.name === "upload_review"}
    onClick={() =>
      navigateWorkspace(selectedPurchaseLines.project_workspace.id, { name: "upload_review" })
    }
    type="button"
  >
    Upload / Review
  </button>
</div>
```

Then split JSX into existing sections guarded by:

```tsx
{workspaceRoute.name === "upload_review" ? (
  <>
    {/* manual-source-form and processing-job-queue */}
  </>
) : null}

{workspaceRoute.name === "review_batch" && activeReviewBatch ? (
  <section className="review-batch-page" aria-label="Review Batch">
    <button
      className="secondary-action"
      onClick={() =>
        navigateWorkspace(selectedPurchaseLines.project_workspace.id, { name: "upload_review" })
      }
      type="button"
    >
      Back to Upload / Review
    </button>
    <div className="view-heading">
      <p className="eyebrow">{activeReviewBatch.review_batch.status}</p>
      <h3>Review Batch #{activeReviewBatch.review_batch.id}</h3>
    </div>
  </section>
) : null}

{workspaceRoute.name === "purchase_lines" ? (
  <>
    {/* existing purchase line empty/table content */}
  </>
) : null}
```

- [ ] **Step 5: Run focused UI test**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx -t "dedicated Review Batch page"
cd ..
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: add workspace tabs and review batch route"
```

---

### Task 7: Add Multi-Candidate Table, Draft Save, And Import Flow

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update test fixture to return multiple candidates and draft endpoint**

In `frontend/src/App.test.tsx`, change the review batch `GET` fixture to return at least two candidates:

```ts
candidates: [
  buildCandidate(20, "PVC pipe", "material", "Plumbing", "Pipes"),
  buildCandidate(21, "PVC elbow", "material", "Plumbing", "Pipes")
],
```

Add helper at file bottom:

```ts
function buildCandidate(
  id: number,
  name: string,
  lineType: "material" | "service",
  topLevelCategory: string,
  subcategory: string
) {
  return {
    id,
    project_workspace_id: 1,
    review_batch_id: 10,
    source_submission_id: 30,
    status: "pending_review",
    proposed_payload: {
      line_type: lineType,
      name,
      quantity: "20",
      unit: "pcs",
      price: "1500",
      currency: "PHP",
      provider_name: "ABC Trading",
      purchase_date: null,
      remarks_or_terms: null,
      category_suggestion: {
        top_level_category: topLevelCategory,
        subcategory
      }
    },
    decision: null,
    merged_into_candidate_id: null,
    reviewed_payload: null,
    taxonomy_gate: null,
    taxonomy_default: null
  };
}
```

Add fixture handling:

```ts
if (url === "/api/project-workspaces/1/review-batches/10/review-draft" && method === "PUT") {
  const body = JSON.parse(String(init?.body));
  return jsonResponse({
    review_batch: {
      id: 10,
      project_workspace_id: 1,
      source_submission_id: 30,
      status: "ready_to_import"
    },
    candidates: body.candidates.map((item: { candidate_id: number; included: boolean; reviewed_payload: unknown }) => ({
      ...buildCandidate(
        item.candidate_id,
        item.candidate_id === 20 ? "PVC pipe" : "PVC elbow",
        "material",
        "Plumbing",
        "Pipes"
      ),
      status: item.included ? "approved_for_import" : "rejected_for_import",
      decision: item.included ? "approved" : "rejected",
      reviewed_payload: item.included ? item.reviewed_payload : null
    })),
    duplicate_groups: [],
    duplicate_conflicts: [],
    taxonomy_decisions: []
  });
}
```

- [ ] **Step 2: Write failing UI test for draft save**

Add:

```ts
test("reviewer saves multi-candidate inclusion draft from the Review Batch page", async () => {
  const user = userEvent.setup();
  const fetchSpy = vi.mocked(fetch);

  render(<App />);

  const selector = await screen.findByRole("navigation", {
    name: "Project Workspace selector"
  });
  await user.click(
    within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
  );
  await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
  await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
  await user.type(
    screen.getByLabelText("Free-form source text"),
    "PVC pipe and PVC elbow, 20 pcs, from ABC Trading, PHP 1,500"
  );
  await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
  await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

  const batch = await screen.findByRole("region", { name: "Review Batch" });
  expect(within(batch).getByText("PVC pipe")).toBeInTheDocument();
  expect(within(batch).getByText("PVC elbow")).toBeInTheDocument();
  const elbowCheckbox = within(batch).getByRole("checkbox", { name: "Include PVC elbow" });
  expect(elbowCheckbox).toBeChecked();
  await user.click(elbowCheckbox);
  expect(elbowCheckbox).not.toBeChecked();

  expect(fetchSpy).not.toHaveBeenCalledWith(
    expect.stringContaining("/review-draft"),
    expect.anything()
  );

  await user.click(within(batch).getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Review draft saved.")).toBeInTheDocument();
  const draftCall = fetchSpy.mock.calls.find(([input]) =>
    input.toString().includes("/review-draft")
  );
  expect(draftCall).toBeDefined();
  expect(JSON.parse(String(draftCall?.[1]?.body))).toEqual({
    candidates: [
      expect.objectContaining({ candidate_id: 20, included: true }),
      expect.objectContaining({ candidate_id: 21, included: false, reviewed_payload: null })
    ]
  });
});
```

- [ ] **Step 3: Run test and verify failure**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx -t "multi-candidate inclusion draft"
cd ..
```

Expected: FAIL because table and Save do not exist.

- [ ] **Step 4: Add draft state and payload builders**

In `frontend/src/App.tsx`, import `saveReviewBatchDraft` and add:

```ts
type CandidateDraft = {
  included: boolean;
  reviewedPayload: ReviewedPurchaseLinePayload | null;
};
```

Add state:

```ts
const [candidateDrafts, setCandidateDrafts] = useState<Record<number, CandidateDraft>>({});
const [toastMessage, setToastMessage] = useState<string | null>(null);
```

Add helper functions outside `App`:

```ts
function reviewedPayloadForCandidate(candidate: ExtractedCandidateRead): ReviewedPurchaseLinePayload {
  const reviewedPayload = candidate.reviewed_payload as ReviewedPurchaseLinePayload | null;
  if (reviewedPayload) {
    return reviewedPayload;
  }
  const proposedPayload = candidate.proposed_payload;
  const suggestion = taxonomySuggestion(candidate);
  return {
    line_type:
      proposedPayload.line_type === "service" || proposedPayload.line_type === "material"
        ? proposedPayload.line_type
        : "material",
    name: String(proposedPayload.name ?? ""),
    top_level_category: suggestion?.topLevelCategory ?? null,
    subcategory: suggestion?.subcategory ?? null,
    quantity: optionalText(String(proposedPayload.quantity ?? "")),
    unit: optionalText(String(proposedPayload.unit ?? "")),
    price: optionalText(String(proposedPayload.price ?? "")),
    currency: optionalText(String(proposedPayload.currency ?? "")),
    provider_name: optionalText(String(proposedPayload.provider_name ?? "")),
    purchase_date: typeof proposedPayload.purchase_date === "string" ? proposedPayload.purchase_date : null,
    remarks_or_terms: optionalText(String(proposedPayload.remarks_or_terms ?? ""))
  };
}

function initialDraftsForCandidates(candidates: ExtractedCandidateRead[]): Record<number, CandidateDraft> {
  return Object.fromEntries(
    candidates.map((candidate) => [
      candidate.id,
      {
        included: candidate.decision !== "rejected",
        reviewedPayload: candidate.decision === "rejected" ? null : reviewedPayloadForCandidate(candidate)
      }
    ])
  );
}
```

In `handleOpenReviewBatch`, after `setActiveReviewBatch(detail)`:

```ts
setCandidateDrafts(initialDraftsForCandidates(detail.candidates));
```

Add checkbox handler:

```ts
function updateCandidateIncluded(candidate: ExtractedCandidateRead, included: boolean) {
  setCandidateDrafts((currentDrafts) => ({
    ...currentDrafts,
    [candidate.id]: {
      included,
      reviewedPayload: included ? reviewedPayloadForCandidate(candidate) : null
    }
  }));
}
```

Add save handler:

```ts
async function handleSaveReviewDraft() {
  if (selectedPurchaseLines === null || activeReviewBatch === null) {
    return null;
  }
  setErrorMessage(null);
  const detail = await saveReviewBatchDraft(
    selectedPurchaseLines.project_workspace.id,
    activeReviewBatch.review_batch.id,
    {
      candidates: activeReviewBatch.candidates.map((candidate) => {
        const draft = candidateDrafts[candidate.id] ?? {
          included: true,
          reviewedPayload: reviewedPayloadForCandidate(candidate)
        };
        return {
          candidate_id: candidate.id,
          included: draft.included,
          reviewed_payload: draft.included ? draft.reviewedPayload : null
        };
      })
    }
  );
  setActiveReviewBatch(detail);
  setCandidateDrafts(initialDraftsForCandidates(detail.candidates));
  setToastMessage("Review draft saved.");
  return detail;
}
```

- [ ] **Step 5: Render candidate table and Save button**

Inside the Review Batch page section, render:

```tsx
{toastMessage ? <p className="toast-message">{toastMessage}</p> : null}
<div className="review-batch-actions">
  <button className="secondary-action" onClick={() => void handleSaveReviewDraft()} type="button">
    Save
  </button>
</div>
<table className="candidate-table">
  <thead>
    <tr>
      <th>Include</th>
      <th>Candidate</th>
      <th>Type</th>
      <th>Category</th>
      <th>Status</th>
      <th>Details</th>
    </tr>
  </thead>
  <tbody>
    {activeReviewBatch.candidates.map((candidate) => {
      const draft = candidateDrafts[candidate.id] ?? {
        included: true,
        reviewedPayload: reviewedPayloadForCandidate(candidate)
      };
      const reviewedPayload = draft.reviewedPayload ?? reviewedPayloadForCandidate(candidate);
      return (
        <tr key={candidate.id}>
          <td>
            <input
              aria-label={`Include ${reviewedPayload.name ?? candidate.proposed_payload.name ?? "candidate"}`}
              checked={draft.included}
              onChange={(event) => updateCandidateIncluded(candidate, event.target.checked)}
              type="checkbox"
            />
          </td>
          <td>{reviewedPayload.name ?? candidate.proposed_payload.name}</td>
          <td>{reviewedPayload.line_type ?? candidate.proposed_payload.line_type}</td>
          <td>
            {reviewedPayload.top_level_category && reviewedPayload.subcategory
              ? `${reviewedPayload.top_level_category} / ${reviewedPayload.subcategory}`
              : "Needs taxonomy"}
          </td>
          <td>{draft.included ? "Included draft" : "Excluded draft"}</td>
          <td>
            <button className="secondary-action" type="button">
              Details
            </button>
          </td>
        </tr>
      );
    })}
  </tbody>
</table>
```

- [ ] **Step 6: Run draft UI test**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx -t "multi-candidate inclusion draft"
cd ..
```

Expected: PASS.

- [ ] **Step 7: Add Import included candidates test**

Append a test that clicks Import and asserts `/review-draft` is called before `/import`, then Purchase Lines is shown:

```ts
test("reviewer imports included candidates after saving the latest draft", async () => {
  const user = userEvent.setup();
  const fetchSpy = vi.mocked(fetch);

  render(<App />);

  const selector = await screen.findByRole("navigation", {
    name: "Project Workspace selector"
  });
  await user.click(
    within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
  );
  await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
  await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
  await user.type(screen.getByLabelText("Free-form source text"), "PVC pipe, 20 pcs");
  await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
  await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

  await user.click(screen.getByRole("button", { name: "Import Included Candidates" }));

  await waitFor(() => {
    expect(window.location.pathname).toBe("/projects/1/purchase-lines");
  });
  expect(await screen.findByRole("heading", { name: "Purchase Lines" })).toBeInTheDocument();
  const calledPaths = fetchSpy.mock.calls.map(([input]) => input.toString());
  expect(calledPaths.findIndex((path) => path.includes("/review-draft"))).toBeLessThan(
    calledPaths.findIndex((path) => path.includes("/import"))
  );
});
```

Implement `handleImportIncludedCandidates`:

```ts
async function handleImportIncludedCandidates() {
  if (selectedPurchaseLines === null || activeReviewBatch === null) {
    return;
  }
  setIsImportingBatch(true);
  setErrorMessage(null);
  try {
    await handleSaveReviewDraft();
    await importReviewBatch(
      selectedPurchaseLines.project_workspace.id,
      activeReviewBatch.review_batch.id
    );
    const refreshedPurchaseLines = await getProjectWorkspacePurchaseLines(
      selectedPurchaseLines.project_workspace.id
    );
    setSelectedPurchaseLines(refreshedPurchaseLines);
    setActiveReviewBatch(null);
    setCandidateDrafts({});
    navigateWorkspace(selectedPurchaseLines.project_workspace.id, { name: "purchase_lines" });
  } catch {
    setErrorMessage("Review Batch could not be imported.");
  } finally {
    setIsImportingBatch(false);
  }
}
```

Add button:

```tsx
<button
  className="primary-action compact-action"
  disabled={isImportingBatch}
  onClick={() => void handleImportIncludedCandidates()}
  type="button"
>
  Import Included Candidates
</button>
```

- [ ] **Step 8: Run full frontend tests**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx
cd ..
```

Expected: all frontend tests pass after updating old expectations that referenced the removed inline single-candidate panel.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: review batch candidate draft UI"
```

---

### Task 8: Add Candidate Detail And Taxonomy Mapping Modal

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add failing UI test for taxonomy mapping preserving draft state**

In `frontend/src/App.test.tsx`, add fixture handler:

```ts
if (url === "/api/project-workspaces/1/review-batches/10/taxonomy-mappings" && method === "POST") {
  return jsonResponse({
    review_batch: {
      id: 10,
      project_workspace_id: 1,
      source_submission_id: 30,
      status: "review_pending"
    },
    candidates: [
      {
        ...buildCandidate(20, "PVC pipe", "material", "Mechanical", "Pipe Materials"),
        reviewed_payload: {
          line_type: "material",
          name: "PVC pipe",
          top_level_category: "Plumbing",
          subcategory: "Pipes",
          quantity: "20",
          unit: "pcs",
          price: "1500",
          currency: "PHP",
          provider_name: "ABC Trading"
        }
      },
      {
        ...buildCandidate(21, "PVC elbow", "material", "Mechanical", "Pipe Materials"),
        reviewed_payload: {
          line_type: "material",
          name: "PVC elbow",
          top_level_category: "Plumbing",
          subcategory: "Pipes",
          quantity: "20",
          unit: "pcs",
          price: "1500",
          currency: "PHP",
          provider_name: "ABC Trading"
        }
      }
    ],
    duplicate_groups: [],
    duplicate_conflicts: [],
    taxonomy_decisions: [
      {
        id: 70,
        project_workspace_id: 1,
        review_batch_id: 10,
        suggested_top_level_category: "Mechanical",
        suggested_subcategory: "Pipe Materials",
        normalized_suggested_path_key: "mechanical / pipe materials",
        decision: "mapped",
        resolved_taxonomy_node_id: 50
      }
    ]
  });
}
```

Add test:

```ts
test("reviewer saves taxonomy mapping and preserves unsaved inclusion choices", async () => {
  const user = userEvent.setup();

  render(<App />);

  const selector = await screen.findByRole("navigation", {
    name: "Project Workspace selector"
  });
  await user.click(
    within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
  );
  await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
  await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
  await user.type(screen.getByLabelText("Free-form source text"), "PVC pipe and PVC elbow");
  await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
  await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

  await user.click(screen.getByRole("checkbox", { name: "Include PVC elbow" }));
  await user.click(screen.getAllByRole("button", { name: "Details" })[0]);
  const detail = await screen.findByRole("dialog", { name: "Candidate Detail" });
  await user.click(within(detail).getByRole("button", { name: "Change Taxonomy" }));
  const taxonomy = await screen.findByRole("dialog", { name: "Resolve Taxonomy" });
  await user.clear(within(taxonomy).getByLabelText("Top-Level Category"));
  await user.type(within(taxonomy).getByLabelText("Top-Level Category"), "Plumbing");
  await user.clear(within(taxonomy).getByLabelText("Subcategory"));
  await user.type(within(taxonomy).getByLabelText("Subcategory"), "Pipes");
  await user.click(within(taxonomy).getByLabelText("Apply to similar taxonomy in this Review Batch"));
  await user.click(within(taxonomy).getByRole("button", { name: "Save Mapping" }));

  expect(await screen.findByText("Plumbing / Pipes")).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "Include PVC elbow" })).not.toBeChecked();
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx -t "taxonomy mapping"
cd ..
```

Expected: FAIL because detail and taxonomy modals do not exist.

- [ ] **Step 3: Add modal state**

In `frontend/src/App.tsx`, add:

```ts
const [detailCandidateId, setDetailCandidateId] = useState<number | null>(null);
const [taxonomyCandidateId, setTaxonomyCandidateId] = useState<number | null>(null);
const [taxonomyForm, setTaxonomyForm] = useState({
  topLevelCategory: "",
  subcategory: "",
  applyToSimilar: false
});
```

Add helpers:

```ts
const detailCandidate = activeReviewBatch?.candidates.find(
  (candidate) => candidate.id === detailCandidateId
) ?? null;
const taxonomyCandidate = activeReviewBatch?.candidates.find(
  (candidate) => candidate.id === taxonomyCandidateId
) ?? null;
```

- [ ] **Step 4: Wire Details button**

Change Details button:

```tsx
<button
  className="secondary-action"
  onClick={() => setDetailCandidateId(candidate.id)}
  type="button"
>
  Details
</button>
```

- [ ] **Step 5: Render Candidate Detail modal**

Add near end of selected workspace section:

```tsx
{detailCandidate ? (
  <div className="modal-backdrop">
    <section aria-label="Candidate Detail" className="modal" role="dialog">
      <div className="view-heading">
        <p className="eyebrow">{detailCandidate.status}</p>
        <h3>Candidate Detail</h3>
      </div>
      <p>{reviewedPayloadForCandidate(detailCandidate).name}</p>
      <p>
        {reviewedPayloadForCandidate(detailCandidate).top_level_category} /{" "}
        {reviewedPayloadForCandidate(detailCandidate).subcategory}
      </p>
      <button
        className="secondary-action"
        onClick={() => {
          const payload = reviewedPayloadForCandidate(detailCandidate);
          setTaxonomyForm({
            topLevelCategory: payload.top_level_category ?? "",
            subcategory: payload.subcategory ?? "",
            applyToSimilar: false
          });
          setTaxonomyCandidateId(detailCandidate.id);
        }}
        type="button"
      >
        Change Taxonomy
      </button>
      <button className="secondary-action" onClick={() => setDetailCandidateId(null)} type="button">
        Close
      </button>
    </section>
  </div>
) : null}
```

- [ ] **Step 6: Render taxonomy modal and save mapping**

Import `saveReviewBatchTaxonomyMapping`. Add handler:

```ts
async function handleSaveTaxonomyMapping() {
  if (
    selectedPurchaseLines === null ||
    activeReviewBatch === null ||
    taxonomyCandidate === null
  ) {
    return;
  }
  const previousDrafts = candidateDrafts;
  const detail = await saveReviewBatchTaxonomyMapping(
    selectedPurchaseLines.project_workspace.id,
    activeReviewBatch.review_batch.id,
    {
      candidate_id: taxonomyCandidate.id,
      top_level_category: taxonomyForm.topLevelCategory,
      subcategory: taxonomyForm.subcategory,
      apply_to_similar: taxonomyForm.applyToSimilar
    }
  );
  setActiveReviewBatch(detail);
  const refreshedDrafts = initialDraftsForCandidates(detail.candidates);
  setCandidateDrafts(
    Object.fromEntries(
      detail.candidates.map((candidate) => [
        candidate.id,
        {
          ...refreshedDrafts[candidate.id],
          included: previousDrafts[candidate.id]?.included ?? refreshedDrafts[candidate.id].included
        }
      ])
    )
  );
  setTaxonomyCandidateId(null);
}
```

Render:

```tsx
{taxonomyCandidate ? (
  <div className="modal-backdrop">
    <section aria-label="Resolve Taxonomy" className="modal" role="dialog">
      <div className="view-heading">
        <p className="eyebrow">Taxonomy Mapping</p>
        <h3>Resolve Taxonomy</h3>
      </div>
      <label>
        Top-Level Category
        <input
          value={taxonomyForm.topLevelCategory}
          onChange={(event) =>
            setTaxonomyForm((current) => ({ ...current, topLevelCategory: event.target.value }))
          }
        />
      </label>
      <label>
        Subcategory
        <input
          value={taxonomyForm.subcategory}
          onChange={(event) =>
            setTaxonomyForm((current) => ({ ...current, subcategory: event.target.value }))
          }
        />
      </label>
      <label className="checkbox-row">
        <input
          checked={taxonomyForm.applyToSimilar}
          onChange={(event) =>
            setTaxonomyForm((current) => ({ ...current, applyToSimilar: event.target.checked }))
          }
          type="checkbox"
        />
        Apply to similar taxonomy in this Review Batch
      </label>
      <button className="primary-action compact-action" onClick={() => void handleSaveTaxonomyMapping()} type="button">
        Save Mapping
      </button>
      <button className="secondary-action" onClick={() => setTaxonomyCandidateId(null)} type="button">
        Cancel
      </button>
    </section>
  </div>
) : null}
```

- [ ] **Step 7: Run focused modal test**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx -t "taxonomy mapping"
cd ..
```

Expected: PASS.

- [ ] **Step 8: Run full frontend tests**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx
cd ..
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: resolve candidate taxonomy from detail modal"
```

---

### Task 9: Final Verification And Cleanup

**Files:**
- Review all modified files.

- [ ] **Step 1: Run backend related tests**

Run:

```powershell
$vars = @{}
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { $vars[$matches[1]] = $matches[2] } }
$password = $vars['POSTGRES_PASSWORD']
$env:HABI_TEST_DATABASE_URL = "postgresql+psycopg://habi:$password@localhost:5432/habi_test"
$env:PYTHONPATH='.'
.\.venv\Scripts\pytest.exe backend/tests/test_review_batch_draft_api.py backend/tests/test_review_batch_taxonomy_mapping_api.py backend/tests/test_ai_extraction_worker.py backend/tests/test_manual_source_import_guards_api.py backend/tests/test_taxonomy_decisions_api.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run frontend tests and build**

Run:

```powershell
cd frontend
npm test -- src/App.test.tsx
npm run build
cd ..
```

Expected: tests and build pass.

- [ ] **Step 3: Inspect diff**

Run:

```powershell
git diff --stat
git diff -- backend/app/review/router.py backend/app/review/schemas.py frontend/src/App.tsx
```

Expected: changes are limited to issue #31 scope. No unrelated refactors.

- [ ] **Step 4: Commit final cleanup when Step 3 produced cleanup changes**

If Step 3 reveals only formatting or small cleanup changes, commit them:

```powershell
git add .
git commit -m "chore: clean up review batch draft implementation"
```

- [ ] **Step 5: Final implementation summary**

Report:

```text
Implemented #31.

Backend:
- Added batch review draft save endpoint.
- Added immediate taxonomy mapping endpoint with exact normalized apply-to-similar behavior.
- Required complete AI taxonomy for visible AI candidates.

Frontend:
- Added Purchase Lines and Upload / Review tabs.
- Added dedicated Review Batch page.
- Added multi-candidate inclusion draft table, Save, Import Included Candidates, Candidate Detail, and taxonomy mapping modal.

Verification:
- backend related tests: PASS
- frontend app tests: PASS
- frontend build: PASS

Known deferral:
- Polished duplicate-group UI remains #16.
```

---

## Self-Review Notes

- Spec coverage: the plan covers project tabs, Upload / Review job queue, dedicated Review Batch page, all candidates displayed, local inclusion draft, batch Save, Import-save-then-import, toast notification, Candidate Detail, taxonomy mapping modal, apply-to-similar, draft preservation, backend validation, AI complete taxonomy, and duplicate deferral to #16.
- Final issue evaluation follow-up: Candidate Detail also needs visible review context from user story 12. Add and verify inclusion status, source submission evidence summary, taxonomy status, and separate Proposed Fields / Reviewed Fields sections before completion.
- Intentional scope choice: purchase-line field editing is only represented through reviewed payload construction and Candidate Detail scaffolding; full field editing is explicitly out of scope for issue #31.
- ADR conflict note: ADR-0064 and ADR-0065 remain true for manual category paths, but issue #31 introduces mapped Taxonomy Decisions for corrections to AI suggestions. The new ADR in Task 1 records that distinction.
