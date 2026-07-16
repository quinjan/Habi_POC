# Implementation Discipline

How agents should implement scoped GitHub issues in this repo.

## Default flow

Implementation work should happen one GitHub issue at a time, in a fresh session when practical.

Each implementation session should receive:

- The PRD issue number.
- Exactly one implementation issue number.
- A clear instruction to implement only that issue's scope.

For the current Per-Project Memory Lab POC, use issue `#1` as the PRD/product context unless superseded by a newer PRD issue.

## Required TDD discipline

All implementation work must use the `tdd` skill.

For each implementation issue:

1. Read the PRD issue and the specific implementation issue.
2. Read `CONTEXT.md`.
3. Read relevant ADRs in `docs/adr/` if they touch the area being changed.
4. Identify the public behavior promised by the implementation issue.
5. Write one failing behavior-level test first.
6. Implement the smallest vertical slice needed to pass that test.
7. Repeat red/green for the next important behavior.
8. Refactor only after tests are green.

Prefer tests through public seams such as API endpoints, UI behavior, generated contracts, or other stable user-facing interfaces. Do not test private functions or implementation details. Do not write all tests upfront before implementation.

## Python test database

When running Python/backend tests, use the local environment's Postgres test database. Set `HABI_TEST_DATABASE_URL` to a dedicated local Postgres database URL before invoking `pytest`, and do not fall back to SQLite for backend behavior tests. The test helpers reset the configured database, so never point `HABI_TEST_DATABASE_URL` at shared, production, or irreplaceable data.

## OpenAI-backed real-model evaluations

Explicit real-model evaluations may call the OpenAI API and may load `OPENAI_API_KEY` from the ignored repository-root `.env`. The local `.env` is a credential source only: never print, copy, snapshot, commit, or include the key in test output, fixtures, exceptions, request logs, or evaluation artifacts.

Keep ordinary unit, behavior, and integration tests deterministic and offline. They must not require an OpenAI credential or make an implicit network call. A real-model evaluation must therefore:

- live in or be marked as an explicit evaluation suite;
- run only through a clearly named opt-in command or marker;
- skip with a clear reason when `OPENAI_API_KEY` is unavailable;
- pin the intended model snapshot and record the prompt/schema version;
- build each evaluation case from its checked-in, versioned fixture manifest rather than ambient Project Memory or mutable database state;
- reject fixtures whose expected result lacks human reviewer identity, approval date, reviewed version, or domain rationale;
- invoke the production Manual Source Entry submission and `ai_manual_free_form_v1` worker path, then score the terminal job and persisted candidate output rather than direct provider output;
- record the fixture ID, fixture version, and deterministic manifest content hash;
- record human prompt/schema versions plus SHA-256 hashes of the production prompt template, fully rendered model input, and canonical structured-output schema;
- compare validated results through strict domain-field assertions rather than raw JSON snapshots, ignoring only documented non-domain transport details;
- disable client-level automatic retries in the primary accuracy profile and classify attempts as pass, model failure, or unscored infrastructure/configuration error;
- report model snapshot, reasoning effort, retry setting, model-call count, validation result, latency, token usage, and estimated cost telemetry when available, without exposing request authorization data;
- generate and schema-validate the compact promotion record after one qualifying 10-call run; do not treat console output alone as promotion evidence;
- never run as a side effect of the normal test command; and
- run in CI only when the evaluation job and its secret are explicitly configured.

For the GPT-5.5 free-form scorecard suite, the primary accuracy evaluation must set `OPENAI_FREE_FORM_RETRIES_ENABLED=false`, disable client-level automatic retries, and complete exactly 10 scored `high`-reasoning calls under one configuration. Calls 1-8 cover every fixture once; calls 9-10 repeat the mixed completed-project baseline and multi-concept installation bundle fixtures. Each fixture must supply its exact source, Contractor Assigned, complete Project Memory, taxonomy vocabulary, and expected result through a checked-in immutable manifest, and the evaluator must seed an isolated Project Workspace from that manifest. All 10 attempts must pass. Any fixture or manifest change or scored model failure requires a new complete 10-call run. A transient API, evaluator, or configuration error with no scorable model outcome makes the current run incomplete; the entire run must start again under a new run ID rather than selectively retrying one fixture. A retry-enabled real-model run is optional, is never part of promotion, and cannot replace a one-pass failure.

Cover `OPENAI_FREE_FORM_RETRIES_ENABLED` and every retry branch with deterministic offline behavior tests. Force zero-result confirmation, whole-result repair, candidate-local repair, retry-disabled behavior, the one-retry maximum, and atomic failure after unsuccessful repair without spending real-model calls.

For the initial POC, strict semantic accuracy is the only hard promotion gate. Every run still records available request and end-to-end latency, input/output/reasoning token usage, and estimated cost with its pricing source. The 10-call report includes p50/p95 latency and total/per-call usage and cost, with infrastructure outcomes and any optional retry-enabled diagnostics separated from primary results. Hard operational thresholds require a later explicit decision based on this baseline and apply only prospectively.

Real-model evaluation setup may seed its isolated Postgres workspace from the fixture manifest, but it must submit and process the free-form entry through the production application boundary and worker. Do not create a parallel evaluation prompt, schema, grounding implementation, or candidate validator. Score the resulting Processing Job, Review Batch, Extracted Candidates, proposed payloads, evidence, and diagnostics. Stop before reviewer edits and final import, which remain covered by offline deterministic tests.

Compute fingerprints from the actual production artifacts immediately before the OpenAI request: UTF-8 prompt/instruction bytes, role-ordered rendered input, and canonical JSON for the response schema. Never include credentials or transport metadata. A change to an output-affecting fingerprint or request parameter requires a new qualifying 10-call promotion run even if its human-readable version was not changed.

After one qualifying run, generate a compact JSON promotion record under `docs/evals/promotions/free-form/`. It must include the complete 10-attempt matrix, identify the eight coverage calls and two sentinel repeats, and include configuration and manifest hashes, safe aggregate metrics, preceding-attempt summaries, and digests for sanitized verbose artifacts. Validate the record against its checked-in schema before accepting promotion. Keep raw request/response payloads and detailed diffs out of Git in ignored local output or access-controlled CI artifacts.

Run the promotion suite only for changes that can affect free-form extraction output or its score: model/request configuration, prompt/context rendering, memory construction, schema/parsing, grounding, semantic validation, calculations, annotation behavior, production processing before candidate persistence, fixtures, comparator, or relevant dependencies. Invoke it through a named manual command or protected manual CI workflow and attach the resulting Promotion Evidence Record to the change. Do not run it for documentation-only, post-extraction review UI, deterministic import, XLSX-only, or unrelated changes. When impact is uncertain, run it. Normal CI always retains offline tests for these components and never implicitly loads the OpenAI key.

Author exactly eight synthetic real-model fixtures: the existing baseline and seven additional realistic, multi-paragraph sources covering the required fixture families. Give each one a primary risk focus while including natural headings, shorthand, shared qualifiers, commercial details, memory distractors, and workflow noise where appropriate. Do not reveal internal schema answers in source wording. Keep minimal single-rule cases in the offline suite.

Do not impose a real-model fixture character-count target or near-limit case. Test source-length acceptance and boundaries deterministically outside the paid model suite.

Require explicit human domain approval for every fixture golden. Store reviewer identity, approval date, fixture version, and domain rationale in the manifest. Do not implement snapshot-update, accept-current-output, or model-self-grading behavior. Any source, context, or expectation change requires a new manifest version, renewed approval, and a new qualifying 10-call promotion run.

## Implementation prompt template

Use this shape when starting a fresh implementation session:

```text
[$tdd](C:\Users\QUINJ3875\.agents\skills\tdd\SKILL.md)

Implement GitHub issue #<implementation-issue-number> for Habi_POC.

Use GitHub issue #1 as the PRD/product context, but only implement the scope described in issue #<implementation-issue-number>.

Before coding:
- Read CONTEXT.md.
- Read relevant ADRs in docs/adr if they touch this area.
- Read issue #1 and issue #<implementation-issue-number> from GitHub.
- Inspect the existing frontend/backend structure before choosing where to edit.

Use test-driven development for this issue:
1. Identify the public behavior the issue promises.
2. Write one failing behavior-level test first.
3. Implement the smallest vertical slice needed to pass.
4. Repeat for the next important behavior.
5. Refactor only after tests are green.

Testing guidance:
- Prefer tests through public seams such as backend API endpoints, generated contracts, or visible UI behavior.
- Do not test private functions or implementation details.
- Run Python/backend tests against the local Postgres test database by setting `HABI_TEST_DATABASE_URL`; do not use SQLite for backend behavior tests.
- Keep normal tests offline. Run OpenAI-backed real-model evaluations only through their explicit opt-in command; they may load `OPENAI_API_KEY` from the ignored repository-root `.env`.
- For the free-form GPT-5.5 scorecard suite, require one complete retry-disabled 10-call promotion run: every fixture once plus repeated mixed-baseline and multi-concept-installation sentinel calls; no retry-enabled real-model run is required.
- Keep tests focused on the scope of issue #<implementation-issue-number>.
- Do not implement future PRD scope unless the issue explicitly requires it.

When done:
- Run the relevant test suite.
- Summarize what changed.
- Mention any skipped tests or remaining risks.
```

## Issue body snippet

Add this to implementation issues that should explicitly carry the repo's implementation discipline:

```md
## Implementation Discipline

This issue must be implemented test-first using the `tdd` skill.

Acceptance for the implementation includes:

- At least one behavior-level failing test written before implementation.
- Tests exercise public behavior, not private internals.
- Relevant test suite passes before completion.
```
