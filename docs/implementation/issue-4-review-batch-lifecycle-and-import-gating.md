# Review Batch Lifecycle And Import Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#4`, adding the full Review Batch lifecycle around Extracted Candidates and enforcing import gates before candidates can enter active Project Memory.

**Architecture:** Keep the API workflow-shaped, but move lifecycle and import rules into small backend services. The backend is the trust boundary for Review Batch status, duplicate conflict checks, close-with-no-import, import eligibility, active Project Memory creation, and evidence promotion.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, pytest. Frontend changes should be minimal and only preserve the existing manual review/import flow; polished Duplicate Candidate Group UI is deferred to issue `#16`.

---

## Source Context

- Parent PRD: GitHub issue `#1`, `PRD: Habi Per-Project Memory Lab POC`
- Implementation issue: GitHub issue `#4`, `Review Batch Lifecycle And Import Gating`
- Blocker complete: GitHub issue `#3`, `Manual Structured Source To Imported Purchase Line`
- Follow-up UI issue: GitHub issue `#16`, `Polished Duplicate Candidate Group Management UI`
- Glossary: `CONTEXT.md`
- Existing agent guidance: `docs/agents/implementation.md`, `docs/agents/github-branch-pr.md`, `docs/agents/domain.md`
- Relevant existing ADRs: `docs/adr/0013-thin-project-scoped-taxonomy-records-for-first-import-slice.md` through `docs/adr/0038-issue-4-is-backend-api-focused-with-polished-duplicate-ui-deferred.md`

## Agreed Decisions

- Persist Review Batch status, but update it only through backend lifecycle rules that recalculate from candidate decisions, duplicate conflicts, and import gates.
- `ready_to_import` means the backend believes import would succeed right now; the import endpoint must still re-check the same gates before writing active Project Memory.
- Pause/resume does not need a paused status or flag in the POC. A reviewer can leave and later continue a non-terminal batch from saved decisions.
- Terminal Review Batch statuses are immutable:
  - `imported`
  - `review_closed_no_import`
- Candidate decisions remain editable until the Review Batch reaches a terminal status.
- Store only the latest candidate review outcome for the POC; full review-action audit history is deferred.
- Candidate decision vocabulary:
  - `approved`: include as an import record.
  - `rejected`: exclude from import. This also covers "removed from import".
  - `merged`: follow another candidate's final include-or-exclude outcome.
  - `null`: unresolved.
- Edited candidates are represented as `approved` candidates whose reviewed payload differs from the proposed payload.
- Duplicate Candidate Groups can be AI-proposed or reviewer-created, and reviewers can add or remove group members.
- Merge actions are valid only within a Duplicate Candidate Group.
- A Duplicate Candidate Group uses one Surviving Candidate that carries the final reviewed payload; there is no group-level import payload.
- A Duplicate Candidate Group can have at most one approved Surviving Candidate.
- Rejected Candidates may remain inside Duplicate Candidate Groups.
- Duplicate conflicts block Review Batch readiness and import.
- Merged Candidates follow their target candidate's final include-or-exclude outcome.
- Unmerge is not a status. It clears merge metadata and returns the candidate to unresolved.
- Import gates apply to approved Surviving Candidates' final reviewed payloads, not to Merged Candidates' original payloads.
- Evidence from Merged Candidates is promoted to the Surviving Candidate's imported Memory Records by default.
- `ready_to_import` requires at least one approved Surviving Candidate whose final reviewed payload satisfies import gates.
- A Review Batch can be closed with no import only when every candidate's final outcome is excluded from import.
- Closing with no import is an explicit reviewer action through a backend workflow endpoint.
- When all candidate outcomes are excluded but the reviewer has not closed the batch, persisted status remains `review_in_progress`; API response may expose that close-with-no-import is available as derived action state.
- Issue `#4` is backend/API-focused. Polished Duplicate Candidate Group UI belongs to issue `#16`.

## Suggested Backend API Shape

Keep existing workflow endpoints and extend them rather than introducing generic CRUD:

- `GET /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}`
  - Return Review Batch status, candidate list, duplicate groups, conflict summary, import readiness, and close-with-no-import availability.
- `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/candidates/{candidate_id}/decision`
  - Support `approved`, `rejected`, and `merged`.
  - For `approved`, accept reviewed payload.
  - For `merged`, accept `merged_into_candidate_id`.
  - Recalculate lifecycle status and conflicts after each change.
- `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/duplicate-groups`
  - Create a Duplicate Candidate Group with member candidates in the same Review Batch.
- `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/duplicate-groups/{duplicate_group_id}/members`
  - Add or remove members through a workflow-shaped request.
- `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/close-with-no-import`
  - Explicitly close a resolved no-import batch.
- `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/import`
  - Import approved Surviving Candidates only after rechecking lifecycle, duplicate conflicts, and import gates.

Endpoint names can be adjusted to fit existing router style, but the API should remain workflow-shaped.

## Data Model Additions

- Add Duplicate Candidate Group persistence scoped to one Project Workspace and one Review Batch.
- Add Duplicate Candidate Group membership for Extracted Candidates.
- Add merge metadata to Extracted Candidates:
  - decision `merged`
  - `merged_into_candidate_id`
- Ensure candidate decisions and duplicate group edits are rejected for terminal Review Batches.
- Consider storing derived conflict details in API responses rather than in database rows unless persistence is truly needed.

## Backend Services

Create small backend services instead of growing router handlers:

- Review Batch lifecycle service:
  - apply candidate decisions
  - clear merge metadata when needed
  - validate terminal immutability
  - validate Duplicate Candidate Group membership
  - detect duplicate conflicts
  - calculate `ready_to_import`
  - calculate close-with-no-import availability
  - update persisted Review Batch status
- Import service:
  - recheck lifecycle and duplicate conflicts
  - validate approved Surviving Candidate import gates
  - import approved Surviving Candidates into active Project Memory
  - promote evidence from Merged Candidates to imported Memory Records
  - mark Review Batch `imported`
- Close-with-no-import service or lifecycle method:
  - reject unresolved or included outcomes
  - mark Review Batch `review_closed_no_import`

## Import Gates

Import must reject when:

- the Review Batch does not belong to the selected Project Workspace
- the Review Batch is terminal
- any candidate lacks a final review outcome
- any Duplicate Candidate Group has unresolved conflicts
- there is no approved Surviving Candidate
- an approved Surviving Candidate lacks source evidence
- an approved Surviving Candidate lacks a resolved category path
- an approved Surviving Candidate for a Purchase Line lacks a linked Material or Service concept
- the batch was already imported

Merged Candidates do not need to satisfy import gates independently because they do not create active Memory Records.

## Duplicate Conflict Rules

Block readiness and import when:

- a Duplicate Candidate Group has more than one approved Surviving Candidate
- a Merged Candidate points outside its Duplicate Candidate Group
- a Merged Candidate points to a candidate in another Review Batch or Project Workspace
- a Merged Candidate points to itself
- merge loops exist
- a Merged Candidate points to a target without a final included or excluded outcome
- a candidate is marked `merged` without `merged_into_candidate_id`
- `merged_into_candidate_id` is present for a non-merged decision

## Test-First Sequence

### Task 1: Extract Lifecycle Calculation From Router

- [ ] Write a failing backend behavior test proving a candidate decision moves a batch from `review_pending` to `review_in_progress`, then to `ready_to_import` only when all candidates have final outcomes and the approved survivor satisfies import gates.
- [ ] Implement the smallest lifecycle service needed to pass.
- [ ] Keep existing manual-source import behavior passing.

Run:

```powershell
pytest backend/tests/test_manual_source_import_api.py backend/tests/test_manual_source_import_guards_api.py -v
```

### Task 2: Explicit Close With No Import

- [ ] Write a failing backend behavior test proving a batch with all rejected candidates remains `review_in_progress` until the close-with-no-import endpoint is called.
- [ ] Test that close-with-no-import rejects unresolved candidates and approved included outcomes.
- [ ] Implement the endpoint and lifecycle rule.

### Task 3: Terminal Immutability

- [ ] Write failing backend behavior tests proving imported and review-closed-with-no-import batches reject candidate decisions, duplicate-group edits, import, and close actions.
- [ ] Implement terminal immutability checks in lifecycle/import services.

### Task 4: Duplicate Group Persistence And Merge Decisions

- [ ] Write failing backend behavior tests for creating a Duplicate Candidate Group, adding/removing members, merging candidates only within the group, and unmerging by clearing merge metadata.
- [ ] Implement the schema, migration, and workflow endpoints.
- [ ] Preserve latest outcome only.

### Task 5: Duplicate Conflict Readiness Guards

- [ ] Write failing backend behavior tests for multiple approved survivors, merge target outside group, self-merge, merge loop, unresolved merge target, and missing merge target.
- [ ] Implement conflict detection and expose conflicts in Review Batch detail.
- [ ] Ensure conflicts block `ready_to_import` and import.

### Task 6: Import Approved Survivors With Merged Evidence

- [ ] Write a failing backend behavior test proving an approved Surviving Candidate imports once while Merged Candidate evidence is attached to the imported Memory Records.
- [ ] Write a test proving Merged Candidate payload gaps do not block import when the Surviving Candidate satisfies gates.
- [ ] Implement survivor-only import and merged evidence promotion.

### Task 7: Contract And Minimal Frontend Compatibility

- [ ] Export OpenAPI after backend API changes.
- [ ] Regenerate frontend API types if the frontend uses generated client types.
- [ ] Make minimal frontend adjustments required to keep the existing manual review/import flow working.
- [ ] Do not implement polished Duplicate Candidate Group UI; leave that to issue `#16`.

## Testing Decisions

- Use behavior-level backend API tests as the primary seam for issue `#4`.
- Prefer public workflow endpoints over private function tests.
- Keep frontend testing minimal unless backend contract changes break the existing manual source review/import flow.
- Good tests prove trust boundaries:
  - candidates do not enter active Project Memory before import
  - `ready_to_import` only appears when backend gates pass
  - import rechecks all gates
  - rejected and merged candidates stay visible in batch history but do not create active memory records
  - duplicate conflicts block readiness and import
  - close-with-no-import is explicit and terminal

## Explicit Deferrals

- Polished Duplicate Candidate Group management UI: issue `#16`.
- AI duplicate detection quality and extraction logic.
- Full review-action audit history.
- Reopening terminal Review Batches.
- Cross-batch or cross-project duplicate detection.
- Group-level reviewed payloads.
- Post-import edit, archive, restore, and value-history workflows.
- Full evidence inspection UI.
- Search/retrieval changes.

## Completion Checklist

- [ ] Backend tests cover Review Batch status transitions.
- [ ] Backend tests cover candidate decision completeness.
- [ ] Backend tests cover no-evidence-no-import.
- [ ] Backend tests cover unresolved taxonomy blocking.
- [ ] Backend tests cover Purchase Line Material/Service linkage blocking.
- [ ] Backend tests cover close-with-no-import behavior.
- [ ] Backend tests cover duplicate group merge/conflict behavior.
- [ ] Backend tests cover terminal immutability.
- [ ] Backend tests cover merged evidence promotion.
- [ ] Relevant OpenAPI/frontend type artifacts are updated if needed.
- [ ] Relevant backend tests pass.
- [ ] No polished duplicate-group UI is implemented in issue `#4`.
