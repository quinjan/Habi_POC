# Free-Form GPT-5.5 Real-Model Evaluation Suite

Implementation status: the eight versioned manifests are checked in under
`backend/evals/free-form/fixtures/` as review drafts. The paid command refuses to run until
every `human_approval.status` is `approved` with complete reviewer metadata. After approval,
run the qualifying suite explicitly (never from ordinary CI):

```powershell
$env:HABI_EVAL_DATABASE_URL = "postgresql+psycopg://.../habi_eval_free_form"
$env:OPENAI_FREE_FORM_MODEL = "gpt-5.5-2026-04-23"
$env:OPENAI_FREE_FORM_REASONING_EFFORT = "high"
$env:OPENAI_FREE_FORM_RETRIES_ENABLED = "false"
$env:OPENAI_CLIENT_MAX_RETRIES = "0"
python backend/scripts/run_free_form_promotion.py
```

The command loads `OPENAI_API_KEY` only from the environment, resets only the explicitly
named eval/test database, uses the production submission/worker/provider boundary, keeps
verbose sanitized artifacts in ignored `.habi-evals/`, and writes a compact checked-in
record only after all ten strict comparisons pass.

This suite measures whether the pinned free-form model, prompt, and structured schema reliably produce grounded candidates across the domain decisions in ADR 0121 through ADR 0150. It is an explicit OpenAI-backed evaluation and is not part of the ordinary offline test command.

## Primary Profile

- Load `OPENAI_API_KEY` only from the local ignored environment configuration.
- Pin `OPENAI_FREE_FORM_MODEL=gpt-5.5-2026-04-23`.
- Set `OPENAI_FREE_FORM_REASONING_EFFORT=high`.
- Set `OPENAI_FREE_FORM_RETRIES_ENABLED=false`.
- Disable OpenAI client or SDK automatic retries for the evaluation request.
- Give each of the eight fixture sources one model call, then repeat the mixed baseline and multi-concept installation fixtures once each.
- Validate model output with the same backend grounding and semantic invariants used by production.
- Preserve every attempted fixture result and report safe model, prompt/schema, call-count, validation, and available usage metadata.

A qualifying promotion run contains exactly 10 scored retry-disabled model calls under one identical configuration:

1. one call for each of the eight required fixtures;
2. one additional call for the mixed completed-project baseline; and
3. one additional call for the multi-concept installation bundle fixture.

All 10 attempts must pass their strict fixture contracts. The two sentinel fixtures must therefore pass twice independently. Any scored model failure fails the complete promotion run; the next attempt starts a new 10-call run, and selectively rerunning only a failed fixture cannot produce promotion evidence.

## Production Execution Boundary

The evaluator must exercise the production Manual Source Entry processing path, not call `OpenAiExtractionProvider.extract_purchase_lines` directly and not maintain an evaluation-only prompt or validator.

For each fixture, the evaluator:

1. creates an isolated Postgres-backed Project Workspace and seeds Contractor Assigned, Project Memory, and taxonomy from the manifest;
2. creates the preserved free-form Manual Source Entry and its queued `ai_manual_free_form_v1` Processing Job through the same application submission boundary used in production;
3. runs the production processing worker with the production-configured OpenAI extraction provider, currently `worker.run_once` dispatching to `process_ai_manual_free_form`;
4. reads the terminal Processing Job, Review Batch, persisted Extracted Candidates, proposed payloads, evidence grounding, and safe diagnostics; and
5. compares that validated persisted result with the fixture contract.

The model-accuracy suite stops before reviewer edits, candidate reset, approval, duplicate resolution, or final Project Memory import. Those behaviors remain deterministic offline tests. If production code later renames or refactors the worker or processor, the evaluator follows the production dispatch path rather than preserving these function names as a parallel compatibility layer.

## Prompt And Schema Fingerprints

Every attempted model call records both human-readable versions and automatic SHA-256 fingerprints for the exact production request contract:

- prompt template version and SHA-256 of the UTF-8 template/instruction bytes;
- SHA-256 of the fully rendered model input, in role/content order, after source and context interpolation and immediately before API transport;
- structured-output schema version and SHA-256 of its canonical JSON representation; and
- the model snapshot, reasoning effort, retry configuration, and other output-affecting request parameters.

The fingerprint input excludes `OPENAI_API_KEY`, authorization headers, API request IDs, timestamps, and other transport metadata. Canonical schema JSON uses deterministic key ordering and separators so property-order-only serialization changes do not create false contract changes. The rendered-input fingerprint remains fixture-specific and complements the fixture-manifest hash by proving the exact manifest context reached the production prompt.

A change to the prompt template hash, schema hash, model snapshot, reasoning effort, or other output-affecting request configuration defines a new evaluation configuration and requires a new qualifying 10-call promotion run, even when a human-readable version was not bumped. A version change with unchanged content is still reported but does not hide the content hashes.

## Promotion Evidence Record

A promotion is not complete until the evaluator generates a compact, schema-validated JSON record and that record is checked in under `docs/evals/promotions/free-form/`. The record is generated from retained run data rather than authored by hand and contains:

- promotion-record schema version, generation time, evaluator version, and repository commit;
- model snapshot, reasoning effort, retry configuration, and other output-affecting request parameters;
- human prompt/schema versions and the prompt-template and canonical-schema SHA-256 hashes;
- every fixture ID, fixture version, manifest hash, and stable rendered-input hash;
- the 10-attempt primary outcome matrix, including the eight-fixture coverage calls, the two defined sentinel repeats, run IDs, exactly-one-call evidence, validation result, and strict comparison result;
- summaries and artifact references for failed or incomplete attempts that preceded the qualifying sequence;
- p50/p95 latency plus total and per-call/per-fixture token and estimated-cost observations, including pricing provenance; and
- SHA-256 digests and storage references for sanitized verbose artifacts.

The checked-in promotion record contains no API key, authorization metadata, raw request or response payload, customer data, or generated database identifiers. Verbose requests, responses, diagnostics, and field-level diffs remain in ignored local evaluation output or access-controlled CI artifact storage. Those artifacts are sanitized before storage and addressed by digest so the compact record can detect replacement or corruption without placing large model payloads in Git.

A missing, manually inconsistent, schema-invalid, or hash-inconsistent promotion record means the configuration is not promoted even if an operator observed passing console output.

## When The Promotion Suite Runs

The 10-call primary promotion suite is explicitly invoked and is not part of ordinary PR CI. A new qualifying promotion record is required when a change can affect free-form extraction output, including changes to:

- model snapshot, reasoning effort, retry-disabled request behavior, or other output-affecting OpenAI parameters;
- prompt instructions, examples, context rendering, ordering, or complete Project Memory construction;
- structured-output schema, response parsing, or response normalization;
- Purchase Line formation, source grounding, memory-match verification, Provider semantics, taxonomy validation, commercial calculation, annotation handling, or atomic-failure rules;
- the production worker/processor path before persisted candidate output;
- fixture manifests, fixture scorecards, the contract comparator, or output-affecting evaluation setup; or
- any dependency upgrade that can change the rendered request, parsed result, or validated candidate payload.

Documentation-only changes, candidate-review UI changes after persisted extraction, deterministic review/import behavior, XLSX-only changes, and unrelated backend changes do not require a real-model promotion run when they cannot affect the free-form production result or evaluation contract. They continue through ordinary credential-free CI.

The relevant change invokes the suite through a clearly named manual command or protected manual CI workflow with explicit secret access. The generated Promotion Evidence Record is attached to that change before its new free-form configuration is considered promotable. If impact is uncertain, treat the change as output-affecting and run the suite. Offline tests for the evaluator, comparator, retry logic, and deterministic invariants remain part of normal CI.

## Initial POC Promotion Metrics

Strict semantic accuracy is the only hard promotion gate for the initial POC. Latency, token usage, and estimated API cost are mandatory observational metrics but do not independently fail an otherwise accurate primary-profile run.

For every model call, record when available:

- end-to-end evaluation duration and OpenAI request duration;
- input, cached-input, output, and reasoning token usage exposed by the API;
- estimated call cost together with the pricing source or pricing snapshot used for that estimate; and
- whether the call belongs to the primary profile or an optional retry-enabled diagnostic.

The 10-call promotion report aggregates at least p50 and p95 latency, total and per-call token usage, and total and per-fixture estimated cost. Scored model calls and unscored infrastructure/configuration attempts are reported separately. After the first qualifying promotion run establishes a baseline, any hard latency, token, or cost threshold requires a new explicit decision and applies prospectively; it does not retroactively invalidate the initial accuracy promotion.

## Fixture Manifest Contract

Every required fixture has one checked-in, versioned manifest that is the complete authority for its evaluation context. The manifest contains:

- stable fixture ID and fixture version;
- exact preserved free-form source text, including line breaks used for character-range verification;
- Contractor Assigned;
- the complete active Project Memory supplied to the model, with stable fixture record IDs, record types, names, resolved taxonomy paths, and Provider Roles where applicable;
- the complete taxonomy vocabulary supplied to the model;
- any other non-secret prompt context required by the production request contract; and
- the exact expected structured result and validation outcome.

The evaluation creates an isolated Project Workspace from the manifest and must not read ambient development, test, or production Project Memory. A run records the manifest version and a deterministic content hash alongside the model and prompt/schema version. Changing source, memory, taxonomy, contractor, or expected output creates a new manifest version and requires a new qualifying 10-call promotion run; historical failed manifests and run records are not rewritten or discarded.

Manifests contain no API keys, credentials, request authorization data, customer data, or mutable external references. `OPENAI_API_KEY` remains local environment state and is never copied into a manifest or report.

## Human-Approved Golden Results

Every fixture manifest contains explicit human domain-approval metadata for its expected result:

- reviewer identity;
- approval date;
- fixture version reviewed; and
- a concise rationale for the intended Purchase Lines, links, Provider semantics, taxonomy, commercial facts, annotations, grounding, and required omissions.

GPT-5.5 or another model may help draft synthetic source text or propose an initial expectation, but model output cannot automatically become or update the golden result. The evaluator provides no record-current-output, approve-on-pass, snapshot-update, or self-grading mode. A fixture without complete human approval metadata is ineligible for a promotion run.

Any change to source text, prompt context, or expected domain output requires a new manifest version and renewed human approval with a change rationale. It also creates a new manifest hash and requires a new qualifying 10-call promotion run. The prior approved manifest, rationale, and evaluation history remain available through version control and retained run records.

## Fixture Authoring Standard

The suite contains exactly eight synthetic, non-customer fixtures: the existing mixed completed-project baseline and seven additional realistic free-form sources. Each source is multi-paragraph or comparably rich and has one primary risk focus while still exercising cross-cutting reading comprehension.

Every real-model fixture should naturally combine several of the following where relevant:

- headings or shared context that apply to multiple candidate spans;
- purchasing shorthand, inconsistent punctuation, and ordinary prose rather than schema-like labels;
- multiple Materials or Services and realistic Provider references;
- shared and candidate-local qualifiers with different annotation targets;
- prices, quantities, packages, exclusions, or availability expressed in varied forms;
- Project Memory matches plus credible unrelated distractors; and
- workflow notes, placeholders, follow-ups, or other source text that must not become purchasing memory.

Fixture wording must not expose the expected answer through artificial labels such as `Bundled Purchase Line`, `annotation target`, or internal schema field names. Vary wording, ordering, values, concept combinations, Provider states, and memory collisions across fixtures. Preserve exact text and line endings in the manifest so grounding remains deterministic.

Small one-sentence examples that isolate a single validator or retry rule belong in deterministic offline tests, not among the eight paid real-model fixtures. A fixture may contain deliberate ambiguity only when its scorecard explicitly requires omission or Unknown behavior; accidental ambiguity is corrected before the manifest version is accepted.

The real-model suite sets no minimum, target, or near-limit source length. Fixture scope is driven by realistic semantic coverage, while source-length acceptance and boundary behavior remain deterministic application tests.

## Result Comparison Contract

Pass or fail is determined by strict field-level comparison after production validation, not by byte-for-byte JSON equality. Every fixture scorecard specifies the exact domain fields it expects, including:

- Purchase Line count and source order;
- exact proposed concept and external Provider names;
- concept types, link counts, link order, and Installation Relationships;
- Provider State, Provider Roles, and null-name invariants;
- proposed Project Memory record IDs or explicit unmatched state;
- top-level categories and subcategories;
- quantities, units, prices, calculated values, source-stated totals, Unknown states, and their provenance;
- annotation count, type, target, target identity, and source order; and
- exact observed text, source excerpts, and backend-verified character ranges.

The comparator may normalize only non-domain transport details: JSON object-property order, generated runtime or database IDs represented by stable fixture references, timestamps, API request IDs, usage telemetry, and equivalent decimal serialization. It must not normalize, fuzzy-match, reorder, or silently discard any expected domain value. Model confidence and other diagnostic telemetry are recorded but are scored only when a fixture explicitly declares them as a product invariant.

A structurally valid but semantically different result fails the fixture and is retained in the evaluation report with field-level differences.

## Outcome Classification

A primary-profile fixture attempt has one of three outcomes:

1. **Pass** - one complete model response survives production validation and matches the strict field-level contract.
2. **Model failure** - the API returns a complete model outcome, but the model refuses, returns invalid or truncated structured output, violates grounding or semantic validation, or differs from the fixture contract. The fixture and complete promotion run fail.
3. **Infrastructure or configuration error** - no scorable model outcome is available because of a connection timeout, rate limit, OpenAI 5xx response, authentication/authorization failure, invalid API request configuration, or evaluator/environment failure. The promotion run is incomplete rather than passed or failed.

Every outcome and safe diagnostic is retained. The primary evaluator performs no automatic API, semantic, or candidate-local retry. After an infrastructure or configuration error, it reruns the entire incomplete 10-call promotion run under a new run ID; rerunning only the affected fixture cannot complete that run. A response that reached application validation is always scored and cannot be reclassified as infrastructure failure merely because it failed validation.

## Required Fixture Families

The eight fixtures consist of the existing baseline plus one additional realistic fixture for each remaining family:

1. **Mixed completed-project baseline** - the four-line Daikin, PVC pipe, site-cleanup, and grout fixture defined in [free-form-gpt-5-5-scorecard.md](free-form-gpt-5-5-scorecard.md), including exact 15-annotation recall and workflow-noise exclusion.
2. **Multi-concept installation bundle** - two or more Materials and at least one installation Service from one Provider with one combined price, explicit many-to-many Installation Relationships, and no fixed link-count truncation.
3. **Partial and multiple service relationships** - multiple Material and Service links where source grounding makes only some relationships installation relationships; mere co-occurrence must not create extra relationships or Provider Roles.
4. **Provider boundary** - commercially related concepts assigned to different Providers must become separate Purchase Lines, with unallocated prices left Unknown and shared total wording retained only as grounded context.
5. **Price attribution and package override** - individually attributable quantities and unit prices produce separate lines unless explicit lot, package, or discount wording establishes one bundled commercial fact; source-stated totals override calculated totals with a visible variance warning.
6. **Finality and workflow noise** - final shorthand and completed work create candidates, while estimates, alternatives, pending work, imperatives, cancellations, status notes, follow-ups, approvals, and placeholders do not.
7. **Annotation targeting and ambiguity** - exact annotation recall, coherent-clause grouping, multi-target replication, transaction-wide targeting, and deliberate omission of qualifiers whose Material, Service, Provider, or Purchase Line target cannot be determined.
8. **Project Memory collision resistance** - overlapping, generic, and tempting unrelated memory entries must not create source-absent concepts, Providers, relationships, categories, or annotations; explicit matched record IDs must remain source-grounded and workspace-valid.

Each fixture receives its own checked-in manifest and exact scorecard. XLSX evaluations are outside this suite because XLSX processing has an independent model and extraction contract.

## Optional Retry-Enabled Diagnostic

No retry-enabled real-model run is required for promotion. Operators may run the same fixture suite with `OPENAI_FREE_FORM_RETRIES_ENABLED=true` as an optional production diagnostic. If run, every fixture must still satisfy the same final scorecard, and the report distinguishes initial-call passes from zero-result confirmations, whole-result repairs, and candidate-local repairs. An `xhigh`-assisted result is diagnostic only and never substitutes for a primary one-pass pass.

Deterministic offline tests must force and verify every centralized retry branch, including retry-disabled failure, zero-result confirmation, whole-result repair, candidate-local repair, one-retry maximum, and atomic failure after unsuccessful repair. Real-model promotion does not depend on those branches being naturally triggered by the fixture suite.
