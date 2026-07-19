# Free-Form GPT-5.4 POC Evaluation

Habi uses one explicit paid evaluation to check output-affecting free-form extraction changes before a human decides whether to merge them. This is a POC confidence check, not a statistically reliable model benchmark or deployment system.

## Fixture

The sole fixture is `backend/evals/free-form/fixtures/01-mixed-completed-project-baseline.json`. It is synthetic, versioned, and human-approved. It combines:

- a bundled supply-and-install Purchase Line;
- a material-only Purchase Line;
- a separately priced delivery Service Purchase Line;
- an internal service Purchase Line;
- an unknown-provider material Purchase Line;
- a specification-bearing reinforcing-steel Purchase Line;
- a second internal service whose lifecycle wording must not enter its reusable name;
- Project Memory context and a memory-only distractor;
- delivery, payment, warranty, availability, exclusion, and Provider annotations; and
- workflow and future-work noise that must not become candidates.

The fixture manifest is the complete evaluation input and golden result. Do not read ambient development or production Project Memory. Changing the fixture or expected result requires a new version and fresh human approval.

## When to run

Run the evaluation for a change that can affect persisted free-form candidate output, including the model/request configuration, prompt or context rendering, structured schema, parsing, grounding, semantic validation, production worker path, fixture, or comparator.

Do not run it for documentation-only, post-extraction review UI, deterministic import, XLSX-only, or unrelated changes.

## Human approval

Every paid call or rerun requires explicit human approval. The agent must stop and ask before invoking the command. A failed result also stops the workflow; diagnose it and obtain fresh approval before another paid call.

## Run

Use a dedicated disposable Postgres evaluation database and the pinned retry-disabled configuration:

```powershell
$env:HABI_EVAL_DATABASE_URL = "postgresql+psycopg://.../habi_eval_free_form"
$env:OPENAI_FREE_FORM_MODEL = "gpt-5.4-2026-03-05"
$env:OPENAI_FREE_FORM_REASONING_EFFORT = "medium"
$env:OPENAI_FREE_FORM_RETRIES_ENABLED = "false"
$env:OPENAI_CLIENT_MAX_RETRIES = "0"
python backend/scripts/run_free_form_evaluation.py --approved-by "<human name>" --prd-issue 36
```

`OPENAI_API_KEY` may come from the ignored repository-root `.env` or environment and must never appear in output or committed files.

The command seeds an isolated Project Workspace, submits the fixture through the production Manual Source Entry API, runs the production worker, makes exactly one model call, and compares the persisted candidates with the fixture golden.

## Pass and fail

The check passes only when:

- exactly one model call occurs;
- the seven expected Purchase Lines match in order and essential fields;
- concept-name comparison treats hyphens and spaces as equivalent punctuation only;
- meaningful singular and plural scope in Service names still matches exactly;
- the expected Provider States, names, prices, and annotation counts match; and
- every required workflow, future-work, placeholder, and Project-Memory-only omission remains absent.

The command prints a short Markdown scorecard:

```md
## Real-Model Evaluation

- PRD: #36
- Fixture: mixed-completed-project-baseline v5
- Model: gpt-5.4-2026-03-05
- Model calls: 1
- Paid call approved by: Quinjan
- Result: PASS
- Purchase Lines: 7/7
- Required exclusions: PASS
- Human merge review: required
```

Post this scorecard to the pull request. A pass does not merge or deploy anything; the human reviewer makes the merge decision. The POC does not generate promotion JSON, schemas, hashes, artifact bundles, sentinel repeats, or ten-call runs.

## Example implementation flow

For a scoped implementation issue under PRD #36 that changes how planned work is excluded:

1. Implement the issue test-first with deterministic offline behavior tests.
2. Run the relevant offline suite.
3. Ask the human to approve one paid fixture call.
4. Run the command and post its scorecard to the PR.
5. On failure, stop, diagnose, and request approval before a rerun.
6. On pass, complete code review and let the human decide whether to merge.
