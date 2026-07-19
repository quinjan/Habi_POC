# Implementation Discipline

How agents should implement scoped GitHub issues in this repo.

## Default flow

Implementation work happens one GitHub issue at a time, in a fresh session when practical.

Each implementation session receives:

- the PRD issue number;
- exactly one implementation issue number; and
- a clear instruction to implement only that issue's scope.

For the current Per-Project Memory Lab POC, use issue `#1` as product context unless a focused successor PRD applies. Free-form GPT-5.5 work uses issue `#36` as its focused PRD.

## Required TDD discipline

All implementation work uses the `tdd` skill.

For each implementation issue:

1. Read the PRD issue and the specific implementation issue.
2. Read `CONTEXT.md`.
3. Read relevant ADRs in `docs/adr/`.
4. Agree with the user on the public behavior and test seams.
5. Write one failing behavior-level test.
6. Implement the smallest vertical slice needed to pass.
7. Repeat red/green for the next important behavior.
8. Refactor only after tests are green.
9. Run the relevant test suite and then use `code-review` against the branch's fixed point.

Prefer public seams such as API endpoints, visible UI behavior, generated contracts, or explicit command-line interfaces. Do not test private functions or implementation details.

## Python test database

Run Python/backend behavior tests against a dedicated local Postgres test database by setting `HABI_TEST_DATABASE_URL`. The helpers reset the configured database, so never point it at shared, production, or irreplaceable data. Do not substitute SQLite for backend behavior tests.

## OpenAI-backed real-model evaluation

Ordinary unit, behavior, and integration tests remain deterministic, offline, and credential-free. A Real-Model Evaluation is an explicit paid POC check for an Output-Affecting Evaluation Change; it is never part of the normal test command or automatic CI.

The POC uses one checked-in fixture: `mixed-completed-project-baseline`. The explicit evaluator:

- seeds an isolated Postgres Project Workspace from that fixture;
- submits its preserved free-form text through the production Manual Source Entry boundary;
- runs the production `ai_manual_free_form_v1` worker path;
- makes exactly one retry-disabled `gpt-5.5-2026-04-23` call at `high` reasoning;
- compares the persisted candidates with the Human-Approved Golden Result; and
- prints a short Markdown PASS-or-FAIL Evaluation Scorecard for the pull request.

Before every paid call or rerun, stop and obtain the user's explicit approval. Pass the approving human's name to the command. A failed evaluation stops implementation: diagnose it, explain the proposed change, and request approval before spending another model call.

Use this command only after offline tests pass:

```powershell
$env:HABI_EVAL_DATABASE_URL = "postgresql+psycopg://.../habi_eval_free_form"
$env:OPENAI_FREE_FORM_MODEL = "gpt-5.5-2026-04-23"
$env:OPENAI_FREE_FORM_REASONING_EFFORT = "high"
$env:OPENAI_FREE_FORM_RETRIES_ENABLED = "false"
$env:OPENAI_CLIENT_MAX_RETRIES = "0"
python backend/scripts/run_free_form_evaluation.py --approved-by "<human name>" --prd-issue 36
```

The command may load `OPENAI_API_KEY` from the ignored repository-root `.env` or environment. Never print, copy, snapshot, commit, or include the credential in fixtures, exceptions, logs, or scorecards.

Run the paid evaluation for changes to the free-form model/request configuration, prompt/context rendering, structured schema, parsing, grounding, semantic validation, production processing before candidate persistence, the fixture, or its comparator. Do not run it for documentation-only, post-extraction review UI, deterministic import, XLSX-only, or unrelated changes.

A passing scorecard is evidence for human review, not automatic deployment. Post the scorecard to the PR and let the human decide whether to merge. No promotion JSON, schema, artifact bundle, sentinel repeat, or ten-call suite is required for the POC.

## Implementation prompt template

```text
[$implement](C:\Users\QUINJ3875\.agents\skills\implement\SKILL.md)

Implement GitHub issue #<implementation-issue-number> for Habi_POC.

Use GitHub issue #<prd-issue-number> as product context, but implement only issue #<implementation-issue-number>.

Before coding:
- Read CONTEXT.md and relevant ADRs.
- Read the PRD and implementation issue from GitHub.
- Inspect the existing frontend/backend structure.
- Propose the public test seams and wait for confirmation.

Use TDD:
1. Write one failing behavior-level test.
2. Implement the smallest vertical slice needed to pass.
3. Repeat for the next important behavior.
4. Refactor only after tests are green.

Keep normal tests offline and run backend behavior tests against the dedicated Postgres test database. If the issue changes free-form extraction output, run the single mixed-baseline Real-Model Evaluation only after offline tests pass and only after explicit human approval for that paid call. Stop and ask again before any rerun.

When done:
- Run relevant tests.
- Use code-review against the branch fixed point.
- Summarize changes, tests, skipped checks, and remaining risks.
- Include the Evaluation Scorecard in the PR when the paid evaluation applies.
```

## Issue body snippet

Add this to implementation issues that change free-form extraction output:

```md
## Implementation Discipline

Implement test-first using the `tdd` skill. Exercise public behavior rather than private internals and run the relevant offline suite before completion.

This is an Output-Affecting Evaluation Change. After offline tests pass, obtain explicit human approval and run the single mixed-baseline Real-Model Evaluation once. Post its Markdown scorecard to the PR. A failure requires diagnosis and fresh human approval before any rerun.
```
