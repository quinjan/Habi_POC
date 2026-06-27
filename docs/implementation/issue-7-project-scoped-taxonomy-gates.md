# Project-Scoped Taxonomy Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `tdd` for implementation. If executing this plan task-by-task, also use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub issue `#7`, adding project-owned taxonomy gate behavior for AI-suggested category paths. Reviewers can approve, map, reject, edit, and rename taxonomy nodes inside one Project Workspace, while only approved or mapped taxonomy decisions influence later default categorization in that same Project Workspace.

**Architecture:** Keep taxonomy learning project-scoped and review-workflow-shaped. Taxonomy gates belong in candidate and Review Batch APIs, because reviewers resolve them while reviewing Extracted Candidates. The Taxonomy module should own project-scoped Taxonomy Nodes, Taxonomy Decisions, default resolution, edit/rename invariants, and no-cross-project learning. Full polished taxonomy management UI is split to issue `#20`.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, Postgres, pytest, React/Vite, generated OpenAPI TypeScript client, Vitest/React Testing Library.

---

## Source Context

- Parent PRD: GitHub issue `#1`, `PRD: Habi Per-Project Memory Lab POC`
- Implementation issue: GitHub issue `#7`, `Project-Scoped Taxonomy Gates`
- Blocker complete: GitHub issue `#4`, `Review Batch Lifecycle And Import Gating`
- Related follow-up UI PRD: GitHub issue `#20`, `Polished Taxonomy Management UI`
- Glossary: `CONTEXT.md`
- Existing agent guidance: `docs/agents/implementation.md`, `docs/agents/github-branch-pr.md`, `docs/agents/domain.md`
- Relevant existing ADRs: `docs/adr/0013-thin-project-scoped-taxonomy-records-for-first-import-slice.md`, `docs/adr/0017-backend-enforced-import-guards.md`, `docs/adr/0030-import-gates-apply-to-approved-surviving-candidates.md`
- Issue-specific ADRs: `docs/adr/0049-new-ai-suggested-taxonomy-paths-require-explicit-decisions.md` through `docs/adr/0071-taxonomy-defaults-are-active-review-assistance.md`

## Agreed Decisions

- `Taxonomy Decision` is a retained project-scoped reviewer judgment on an AI-suggested category path: approve, map, or reject.
- `Taxonomy Decision` is separate from candidate review outcome. Candidate removal from import uses the existing Rejected Candidate outcome.
- Any AI-suggested category path that would create a new project taxonomy node requires an explicit Taxonomy Decision before affected approved Surviving Candidates can be imported.
- Top-Level Category and subcategory suggestions use the same gate level in the POC.
- A candidate can be approved before its Taxonomy Gate is resolved, but the Review Batch cannot become ready to import until every approved Surviving Candidate has a Resolved Category Path and satisfies import gates.
- Approved and mapped Taxonomy Decisions can influence later default categorization only inside the same Project Workspace.
- Rejected Taxonomy Decisions are retained for analysis and review continuity, but do not influence future defaults.
- For the same normalized suggested path inside a Project Workspace, the latest Taxonomy Decision wins for gate display, prior rejection context, and future default resolution.
- Future identical AI suggestions after a rejected Taxonomy Decision should appear again as unresolved Taxonomy Gates with prior rejection context, not be silently suppressed.
- Rejecting a taxonomy suggestion does not reject the affected Extracted Candidate.
- Habi does not persist deferred Taxonomy Decisions in the POC. A reviewer who is not ready to decide leaves the Taxonomy Gate unresolved.
- One Taxonomy Decision can resolve multiple candidates with the same normalized AI-suggested category path inside the selected Project Workspace.
- Suggestion matching uses normalized exact paths: trim whitespace and case-fold each path segment, then compare the full two-level path. No fuzzy matching, synonyms, or aliases in this slice.
- Resolved Category Paths are exactly two levels for the POC: Top-Level Category and subcategory.
- Top-level-only suggestions remain unresolved for import because Resolved Category Paths require both a Top-Level Category and subcategory.
- Top-level-only suggestions should show an unresolved Taxonomy Gate with a subcategory-required reason even when the Top-Level Category already exists.
- Approved Taxonomy Decisions must include a complete two-level path.
- Mapped Taxonomy Decisions must point to an existing subcategory leaf node in the same Project Workspace, not a Top-Level Category node.
- Suggestions that match an existing approved taxonomy path in the selected Project Workspace do not require a Taxonomy Gate.
- Manual reviewer-supplied category paths can create or reuse Taxonomy Nodes at import time without recording a Taxonomy Decision.
- Manual category paths do not create remembered AI suggestion mappings.
- New Project Workspaces start with no seed taxonomy for the POC.
- Taxonomy Nodes and Taxonomy Decisions belong to exactly one Project Workspace.
- Taxonomy Decisions made during review should reference their originating Review Batch and affected AI-suggested category path for traceability.
- Taxonomy Decisions can only be created for normalized AI-suggested paths that appear among candidates in the referenced Review Batch and Project Workspace.
- Taxonomy Gate decisions cannot be changed after a Review Batch reaches a terminal status.
- Approved Taxonomy Decisions create or reuse taxonomy nodes immediately, and those nodes remain even if the originating Review Batch later closes with no import.
- Taxonomy Node names must be unique among siblings inside one Project Workspace after normalization, enforced by a database-level uniqueness constraint and application-level validation.
- The same subcategory name may exist under different parent nodes.
- Taxonomy node rename/edit workflows update live displayed Resolved Category Paths for imported Memory Records that reference those nodes.
- Full import-time taxonomy history is left for a later audit/history slice.
- Taxonomy gates apply to all imported Memory Records, not only Purchase Lines.
- Purchase Lines may still have additional import gates, such as requiring a linked Material or Service concept.
- Taxonomy defaults should be returned with candidate and Review Batch APIs, not through a standalone default-resolution endpoint in this slice.
- Taxonomy defaults can auto-fill reviewed category fields, but the UI must disclose provenance and reviewers can change the category before approval.
- Taxonomy defaults are active-review assistance only. Terminal batch views should show retained decisions, reviewed payloads, and gate history read-only rather than suggesting new editable defaults from later taxonomy decisions.
- Provenance text should distinguish approved-category reuse from previous mapping reuse.
- Rejected Taxonomy Decisions and unresolved Taxonomy Gates should remain visible in the affected Review Batch while non-terminal, with clear status text.
- Separate analytics or scorecard UI for taxonomy decisions is out of scope.
- Polished standalone taxonomy management UI is out of scope for `#7` and belongs to `#20`.

## Suggested Domain Model

### Taxonomy Node

Existing Taxonomy Nodes should remain project-scoped and parent-child based. For this slice:

- Enforce sibling uniqueness by normalized name within one Project Workspace and parent.
- Store `normalized_name` on `TaxonomyNode` using trim, whitespace-collapse, and case-fold normalization for sibling uniqueness and lookup.
- Handle root Top-Level Category uniqueness explicitly despite nullable `parent_id`, such as with separate root and child unique indexes or an equivalent coalesced/generated parent key.
- Support exactly two levels for Resolved Category Paths in review/import behavior.
- Allow name-only edit/rename within the selected Project Workspace; do not support reparenting in issue `#7`.
- Ensure live category-path display can be derived from current node names or kept in sync when denormalized rows exist.

### Taxonomy Decision

Add project-scoped Taxonomy Decision persistence for AI-suggested category paths.

Suggested fields:

- `id`
- `project_workspace_id`
- `review_batch_id`, nullable only if future non-review origins need it; gate decisions should set it
- `suggested_top_level_category`
- `suggested_subcategory`
- normalized suggested path fields or a normalized path key
- `decision`, one of `approved`, `mapped`, `rejected`
- `resolved_taxonomy_node_id`, set to a subcategory leaf node for approved or mapped decisions
- `created_at`

Optional fields if helpful:

- affected candidate IDs through a join table or response-level derivation
- reviewer-facing provenance text can be derived rather than stored

Do not build an alias table. Mapped decisions remember an exact normalized AI-suggested path and the existing approved project Taxonomy Node it maps to.

## Suggested Backend API Shape

Keep endpoints Project Workspace-scoped and workflow-shaped. Names may adjust to existing router conventions.

- `GET /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}`
  - Include candidates, raw AI category suggestions, taxonomy gate state, defaulted reviewed category path, provenance text, and a lightweight `taxonomy_decisions` list scoped to decisions originating in the batch.
- `POST /api/project-workspaces/{project_workspace_id}/review-batches/{review_batch_id}/taxonomy-decisions`
  - Resolve one suggested path with `approved`, `mapped`, or `rejected`.
  - For `approved`, require a complete two-level path and create or reuse the approved project Taxonomy Nodes immediately.
  - For `mapped`, require an existing subcategory leaf Taxonomy Node in the same Project Workspace.
  - For `rejected`, retain the decision but do not create defaults.
  - Validate that the normalized suggested path appears among candidates in the referenced Review Batch and Project Workspace.
  - Apply the decision to matching unresolved suggestions in the Review Batch.
  - Return the updated `ReviewBatchDetail` so the frontend can refresh affected gates/defaults without guessing.
- `PATCH /api/project-workspaces/{project_workspace_id}/taxonomy-nodes/{taxonomy_node_id}`
  - Minimal name-only edit/rename endpoint needed by `#7`, guarded by project scope and sibling uniqueness. Reparenting is out of scope.
  - Return the updated Taxonomy Node plus its current two-level category path.
- `GET /api/project-workspaces/{project_workspace_id}/taxonomy-nodes?leaf_only=true`
  - Return selectable existing two-level leaf category paths for the map UI, scoped to the selected Project Workspace.

Avoid a standalone taxonomy-default resolution endpoint in this slice. Return defaults with candidate/review data. Candidate approval should persist reviewed category fields, but manual category paths should create or reuse Taxonomy Nodes only at import time while creating Project Memory.

## Review API Response Guidance

Review candidate responses should expose enough information for a reviewer to distinguish AI suggestion, project-local default, and reviewed category fields.

Decision-rich shape:

```json
{
  "id": 42,
  "proposed_payload": {
    "name": "PVC pipe",
    "category_suggestion": {
      "top_level_category": "Mechanical",
      "subcategory": "Pipe Materials"
    }
  },
  "taxonomy_gate": {
    "status": "resolved_by_mapping",
    "reason": "mapped_taxonomy_decision",
    "suggested_category_path": "Mechanical / Pipe Materials",
    "resolved_category_path": "Plumbing / Pipes",
    "decision": "mapped",
    "taxonomy_decision_id": 17
  },
  "taxonomy_default": {
    "resolved_category_path": "Plumbing / Pipes",
    "source": "mapped_taxonomy_decision",
    "provenance_text": "Defaulted from a previous mapping: Mechanical / Pipe Materials -> Plumbing / Pipes"
  }
}
```

Exact field names can change to fit existing schemas, but the public behavior should remain:

- raw AI suggestion remains visible
- taxonomy gate state uses structured status/reason values such as `new_taxonomy_path`, `subcategory_required`, `resolved_by_approval`, and `resolved_by_mapping`
- prior rejection context is exposed as separate gate context rather than replacing the current unresolved gate status/reason
- gate/default/prior-rejection context should include the relevant latest `taxonomy_decision_id` when it comes from a retained Taxonomy Decision
- defaulted path can auto-fill reviewed category fields
- provenance is visible in UI
- reviewer can override before approval
- import readiness still rechecks Resolved Category Path
- `ReviewBatchDetail` includes lightweight retained Taxonomy Decision history for the batch, while candidate-level fields carry the active gate/default context

## Import And Readiness Rules

Import readiness must reject when:

- an approved Surviving Candidate lacks a Resolved Category Path
- an approved Surviving Candidate only has a Top-Level Category
- an approved Surviving Candidate references a taxonomy node outside the selected Project Workspace
- a mapped decision points to a taxonomy node outside the selected Project Workspace or to a Top-Level Category node
- the Review Batch is terminal and a taxonomy decision or candidate category edit is attempted

Import readiness should not reject merely because:

- rejected candidates have unresolved taxonomy
- merged candidates have unresolved taxonomy when their Surviving Candidate satisfies gates
- an exact existing approved taxonomy path was suggested without a Taxonomy Decision row

## Minimal Frontend Scope

In scope:

- Show Taxonomy Gates in the review flow for affected candidates.
- Show Taxonomy Gates for AI-suggested category paths that would create new project taxonomy.
- Let reviewers approve, map, or reject an AI-suggested category path.
- For mapping, use a simple search/select over existing two-level leaf category paths in the selected Project Workspace.
- Let reviewers remove the affected candidate from import using the existing rejected candidate outcome.
- Auto-fill reviewed category fields when a project-local taxonomy default exists.
- Show hover or info text for default provenance.
- Show rejected taxonomy decisions and unresolved Taxonomy Gates in the non-terminal Review Batch context.

Rename/edit behavior for Taxonomy Nodes is required in backend API and behavior tests for issue `#7`, but polished or visible taxonomy-management controls are deferred to issue `#20`.

Out of scope:

- Full taxonomy tree manager.
- Taxonomy analytics or scorecard UI.
- Alias management.
- Cross-project taxonomy learning.
- Global/company taxonomy.
- Bulk merge/split/reparent workflows.
- Full audit history of taxonomy node edits.

## Test-First Sequence

### Task 1: Taxonomy Decision Persistence And Project Scope

- [ ] Write a failing backend behavior test proving a Taxonomy Decision belongs to one Project Workspace and cannot map to a Taxonomy Node in another Project Workspace.
- [ ] Implement Taxonomy Decision model, migration, and minimal project-scoped creation path.
- [ ] Keep existing import and review tests passing.

### Task 2: New AI-Suggested Taxonomy Path Gate

- [ ] Write a failing backend behavior test proving an AI-suggested new taxonomy path creates a Taxonomy Gate and blocks ready-to-import for an approved candidate until resolved.
- [ ] Implement gate detection for AI-suggested paths that would create new project taxonomy nodes.
- [ ] Prove top-level-only categorization remains unimportable.

### Task 3: Subcategory And Existing Path Resolution

- [ ] Write a failing backend behavior test proving a new subcategory under an existing Top-Level Category requires the same explicit Taxonomy Decision as other new AI-suggested taxonomy paths.
- [ ] Write a test proving an exact existing approved taxonomy path does not require a Taxonomy Gate.
- [ ] Implement exact normalized path matching and two-level path enforcement.

### Task 4: Approve, Map, Reject

- [ ] Write failing backend behavior tests for approving a new taxonomy path, mapping a suggestion to an existing path, and rejecting a suggestion.
- [ ] Prove approved and mapped decisions resolve import readiness.
- [ ] Prove approved decisions require a complete two-level path.
- [ ] Prove mapped decisions require an existing subcategory leaf node in the same Project Workspace.
- [ ] Prove taxonomy decisions are rejected when the suggested path does not appear in the referenced Review Batch.
- [ ] Prove rejected decisions do not influence defaults.
- [ ] Prove unresolved Taxonomy Gates do not resolve import readiness.
- [ ] Prove rejecting a taxonomy suggestion does not reject the candidate.

### Task 5: Matching Suggestions And Defaults

- [ ] Write a failing backend behavior test proving one Taxonomy Decision resolves repeated normalized matching suggestions in the same Review Batch.
- [ ] Write a test proving the latest Taxonomy Decision wins for a repeated normalized suggestion path.
- [ ] Write a test proving approved and mapped decisions influence later candidate defaults only in the same Project Workspace.
- [ ] Write a test proving taxonomy learning does not cross Project Workspace boundaries.
- [ ] Implement default resolution in candidate or Review Batch responses.
- [ ] Include provenance text or structured provenance fields for the frontend.
- [ ] Include prior rejection context for matching unresolved gates when the latest retained decision for that suggestion was rejected.

### Task 6: Candidate Approval Before Taxonomy Resolution

- [ ] Write a failing backend behavior test proving a candidate can be approved while taxonomy is unresolved, but the Review Batch remains not ready to import.
- [ ] Implement candidate/review response state that distinguishes approved from importable.
- [ ] Recheck import gates at import time.

### Task 7: Rename/Edit Taxonomy Nodes

- [ ] Write a failing backend behavior test proving taxonomy leaf path listing is scoped to the selected Project Workspace.
- [ ] Write failing backend behavior tests for renaming a Taxonomy Node inside the selected Project Workspace.
- [ ] Test duplicate sibling name rejection after normalization.
- [ ] Test database-level normalized sibling uniqueness, with application-level validation returning a clear error.
- [ ] Test duplicate root Top-Level Category names are rejected after normalization.
- [ ] Test same subcategory name is allowed under different parents.
- [ ] Test Project Workspace boundaries for edit/rename.
- [ ] Test rename/edit rejects reparenting attempts.
- [ ] Test live displayed Resolved Category Paths reflect the new node name.
- [ ] Implement minimal edit/rename endpoint and supporting display behavior.

### Task 8: Minimal Frontend Review Flow

- [ ] Write a failing frontend behavior test proving a reviewer sees a Taxonomy Gate for a new AI-suggested taxonomy path and can resolve it.
- [ ] Write a test proving a project-local mapped default auto-fills reviewed category fields and shows provenance text.
- [ ] Implement minimal review UI controls for approve, map, reject, and remove-from-import.
- [ ] Implement mapping with a simple search/select over existing two-level leaf category paths only.
- [ ] Do not implement the standalone polished taxonomy manager from issue `#20`.

### Task 9: Contract And Generated Types

- [ ] Export OpenAPI after backend API changes.
- [ ] Regenerate frontend API types if the frontend uses generated client types.
- [ ] Update frontend API client wrappers.
- [ ] Run relevant backend and frontend tests.

## Testing Decisions

- Use behavior-level backend API tests as the primary backend seam.
- Use frontend behavior tests for active review behavior: gate resolution controls, taxonomy default provenance display, prior rejection context, and project-scoped mapping options.
- Do not require frontend terminal/history display tests for rejected Taxonomy Decisions in issue `#7`; retained history should be covered by backend behavior tests.
- Prefer public workflow endpoints and visible UI behavior over private function tests.
- Run backend behavior tests against Postgres, following the existing repo direction.
- Good tests prove trust boundaries:
  - taxonomy nodes and decisions are project-scoped
  - taxonomy learning does not cross Project Workspace boundaries
- top-level-only categorization is not importable
  - every imported Memory Record requires a Resolved Category Path
  - rejected decisions are retained but do not affect future defaults
  - approved and mapped decisions affect future defaults only inside the same Project Workspace
  - terminal Review Batches reject taxonomy decision changes
  - approved taxonomy nodes survive review closed with no import

## Explicit Deferrals

- Polished taxonomy management UI: issue `#20`.
- Taxonomy aliases.
- Fuzzy or synonym matching.
- Arbitrary-depth taxonomy paths.
- Global or company-level taxonomy.
- Cross-project taxonomy learning.
- Taxonomy analytics or scorecard UI.
- Full taxonomy edit audit history.
- Bulk taxonomy merge, split, or reparent workflows.
- Search/retrieval ranking changes.

## Required Changes From Current Patch

Use this checklist to bring the current partial issue `#7` patch up to acceptance:

### Backend Lifecycle And Import Gates

- [ ] Fix `ready_to_import` so it requires every approved Surviving Candidate to satisfy import gates, not merely any approved candidate.
- [ ] Keep rejected candidates and merged candidates from blocking when the approved Surviving Candidate is importable.
- [ ] Re-check the same gates in the import endpoint so a stale or incorrect `ready_to_import` status cannot allow partial import.
- [ ] Ensure unresolved taxonomy gates, top-level-only reviewed category paths, missing reviewed category paths, and out-of-project taxonomy references keep approved Surviving Candidates unimportable.

### Taxonomy Decision Semantics

- [ ] Remove `deferred` from API schemas, persistence validation, frontend generated types, UI controls, and tests.
- [ ] Keep Taxonomy Decisions limited to `approved`, `mapped`, and `rejected`.
- [ ] Require Taxonomy Decisions to reference a normalized AI-suggested path that appears in the selected Review Batch and Project Workspace.
- [ ] Apply the same explicit gate level to any AI-suggested path that would create new project taxonomy, whether Top-Level Category or subcategory.
- [ ] Treat exact existing two-level project taxonomy paths as no-gate classifications.
- [ ] Show top-level-only suggestions as unresolved gates with a subcategory-required reason, even if the Top-Level Category already exists.
- [ ] Use latest Taxonomy Decision wins per normalized suggested path inside the Project Workspace.
- [ ] Keep rejected decisions from resolving gates or creating defaults; future identical suggestions should reappear as unresolved gates with prior rejection context.

### Taxonomy Nodes

- [ ] Add stored `normalized_name` to `TaxonomyNode` and compute it only in the backend.
- [ ] Enforce normalized sibling uniqueness at the database level and through application validation.
- [ ] Handle root Top-Level Category uniqueness explicitly despite nullable `parent_id`.
- [ ] Require `approved` Taxonomy Decisions to include a complete two-level path and create/reuse nodes immediately.
- [ ] Require `mapped` Taxonomy Decisions to target an existing subcategory leaf node in the same Project Workspace.
- [ ] Keep approved taxonomy nodes even if the originating Review Batch later closes with no import.
- [ ] Add project-scoped leaf-path listing for map controls, returning only complete two-level leaf paths.
- [ ] Add name-only taxonomy node rename/edit endpoint with project-boundary checks, sibling uniqueness, no reparenting, and response containing the updated node plus current two-level path.

### Review Responses And Contracts

- [ ] Make `POST taxonomy-decisions` return the updated `ReviewBatchDetail`.
- [ ] Add candidate-level `taxonomy_gate`, `taxonomy_default`, and prior rejection context with structured status/reason fields.
- [ ] Include the relevant latest `taxonomy_decision_id` for resolved/default/prior-rejection context.
- [ ] Add lightweight batch-scoped `taxonomy_decisions` history to `ReviewBatchDetail`.
- [ ] Compute taxonomy defaults from retained decisions across the same Project Workspace using latest-decision-wins.
- [ ] Keep taxonomy defaults as active-review assistance only; terminal batch views should not suggest new editable defaults from later decisions.
- [ ] Do not mutate candidate `reviewed_payload` when defaults exist. Persist category fields only when reviewer approval submits them.

### Frontend Review Flow

- [ ] Add review-time controls to approve, map, reject, and remove affected candidates from import.
- [ ] Add simple search/select mapping over project-scoped two-level leaf taxonomy paths only.
- [ ] Auto-fill reviewed category fields from taxonomy defaults in frontend state, with provenance visible and editable before approval.
- [ ] Show prior rejection context as warning-like context on unresolved gates without making it a separate blocking rule.
- [ ] Do not build visible rename/edit taxonomy management controls for issue `#7`; backend endpoint and behavior tests are enough.

### Tests And Generated Artifacts

- [ ] Add backend behavior tests for all backend lifecycle, taxonomy decision, taxonomy node, and response-contract rules above.
- [ ] Add frontend behavior tests for active review gate controls, default provenance, prior rejection context, and project-scoped map options.
- [ ] Regenerate OpenAPI and frontend API types after backend schema changes.
- [ ] Run relevant backend and frontend test suites before completion.

## Completion Checklist

- [ ] Backend tests cover project-scoped Taxonomy Decisions.
- [ ] Backend tests cover AI-suggested new taxonomy path gates.
- [ ] Backend tests cover top-level-only categorization blocking import.
- [ ] Backend tests cover approve, map, and reject taxonomy decisions.
- [ ] Backend tests cover taxonomy decision creation only for suggestions present in the referenced Review Batch.
- [ ] Backend tests cover repeated normalized suggestion resolution.
- [ ] Backend tests cover latest Taxonomy Decision wins for gate display and future defaults.
- [ ] Backend tests cover approved/mapped defaults staying inside one Project Workspace.
- [ ] Backend tests prove taxonomy learning does not cross Project Workspace boundaries.
- [ ] Backend tests cover rejected decisions not affecting defaults.
- [ ] Backend tests cover repeated rejected suggestions appearing as unresolved gates with prior rejection context.
- [ ] Backend tests cover approved taxonomy nodes surviving review closed with no import.
- [ ] Backend tests cover project-scoped taxonomy leaf path listing for map controls.
- [ ] Backend tests cover taxonomy node edit/rename and sibling uniqueness.
- [ ] Backend tests cover live displayed Resolved Category Paths after rename.
- [ ] Frontend tests cover review-time taxonomy gate controls.
- [ ] Frontend tests cover taxonomy default provenance display.
- [ ] Frontend tests cover prior rejection context in active review.
- [ ] Frontend tests cover map controls using only selected-Project Workspace taxonomy paths.
- [ ] Relevant OpenAPI/frontend type artifacts are updated if needed.
- [ ] Relevant backend and frontend tests pass.
- [ ] No standalone polished taxonomy management UI is implemented in issue `#7`.
