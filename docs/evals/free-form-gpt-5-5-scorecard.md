# Free-Form GPT-5.5 Regression Scorecard

This scorecard defines the required real-model result for the completed-project source in `outputs/issue-9-purchase-line-detail-test-data/Issue_9_Free_Form_Manual_Source.txt`. The evaluation uses the pinned free-form model and prompt/schema version recorded by the Processing Job.

The scorecard runs as part of an explicitly invoked promotion suite only when an output-affecting free-form model, prompt, schema, processing, validation, or fixture change requires new evidence. It is not part of ordinary PR CI.

This source is the first of eight realistic synthetic fixtures. The remaining seven fixtures follow the suite's multi-paragraph authoring standard; isolated one-rule cases remain deterministic offline tests.

Its manifest expectation is a human-approved golden result. No model response may overwrite or automatically update the expected four lines, seven taxonomy paths, 15 annotations, grounding, or exclusions.

## Execution Profiles

This is an explicit OpenAI-backed evaluation, not part of the ordinary offline test suite. It may load `OPENAI_API_KEY` from the ignored repository-root `.env`; the credential must never appear in logs, fixtures, snapshots, exceptions, or committed artifacts. If the key is unavailable, the evaluation skips with a clear reason instead of silently substituting a mock result.

Run and report two profiles independently:

1. **Primary one-pass accuracy:** set `OPENAI_FREE_FORM_RETRIES_ENABLED=false`, use the pinned `gpt-5.5-2026-04-23` snapshot at `high` reasoning, and require the complete scorecard from exactly one model call.
2. **Optional retry-enabled diagnostic:** set `OPENAI_FREE_FORM_RETRIES_ENABLED=true`, require the same final scorecard, and report whether the initial `high` call passed or one permitted `xhigh` confirmation or repair call was required. This profile is not required for promotion.

A retry-assisted diagnostic pass is not a one-pass accuracy pass. Each run records the model snapshot, prompt/schema version, reasoning effort, retry setting, model-call count, validation result, and token/cost telemetry when available.

This scorecard is one required fixture in the complete suite defined by `free-form-gpt-5-5-suite.md`. Its run input comes only from its checked-in, versioned fixture manifest; the evaluator seeds an isolated Project Workspace and records the manifest content hash. During development, one fixture attempt provides feedback but does not qualify a change for promotion. A qualifying promotion run contains 10 scored calls: one for each of the eight fixtures plus one repeat of this mixed baseline and one repeat of the multi-concept installation fixture. All 10 attempts must pass. Any scored failure or fixture-manifest change requires a new complete 10-call promotion run. The report preserves all attempted runs rather than discarding failures from promotion history.

Every attempt records the human prompt/schema versions plus SHA-256 fingerprints of the production prompt template, fully rendered model input, and canonical structured-output schema. All 10 promotion attempts use identical prompt-template and schema fingerprints; each repeated fixture retains the same rendered-input fingerprint.

The result under test is the terminal Processing Job and its production-persisted Review Batch and Extracted Candidates after the `ai_manual_free_form_v1` worker path completes. Direct provider output is not scored as a substitute, and the fixture stops before reviewer interaction or final import.

## Required Purchase Lines

The result contains exactly four source-ordered Purchase Lines:

1. Bundled Daikin split-type air-conditioning supply and installation with one Material, one Service, one grounded Installation Relationship, combined PHP 120,000 price, and external CoolAir Mechanical Services Provider.
2. Material-only 100 mm PVC pressure pipe purchase for PHP 32,500 with external BuildMart Trading Provider. The separate PHP 1,500 delivery charge remains an annotation, not a fifth Service Purchase Line.
3. Service-only final site cleanup for PHP 18,000 with Internal Provider State, null Provider name, and exact observed internal wording.
4. Material-only non-shrink grout purchase for PHP 8,500 with Unknown Provider State and null Provider name.

The output contains no `Ceiling installation` concept or other Project-Memory-only fact.

## Required Taxonomy Paths

The seven candidate subjects retain these complete two-field paths:

1. Material: `Electrical / Air Conditioning Equipment`
2. Service: `Services / Air Conditioning Installation`
3. Provider: `Providers / HVAC Contractors`
4. Material: `Plumbing / Pipes`
5. Provider: `Providers / Construction Material Suppliers`
6. Service: `Services / Site Cleanup`
7. Material: `Civil / Grouting Materials`

## Required Evidence Annotations

The result contains exactly 15 annotations:

| # | Candidate | Type | Target | Required source meaning |
|---:|---|---|---|---|
| 1 | Daikin bundle | Delivery terms | Purchase Line | Delivery and unloading included |
| 2 | Daikin bundle | Payment terms | Purchase Line | 50% down and 50% after testing and commissioning |
| 3 | Daikin bundle | Validity terms | Purchase Line | Combined price valid for 30 calendar days |
| 4 | Daikin bundle | Warranty terms | Material | Five-year compressor warranty |
| 5 | Daikin bundle | Warranty terms | Service | One-year installation workmanship warranty |
| 6 | Daikin bundle | Availability terms | Material | Units available from local stock |
| 7 | Daikin bundle | Condition or exclusion | Purchase Line | Electrical feeder wiring beyond five meters excluded |
| 8 | Daikin bundle | General qualifier | Provider | CoolAir is an authorized Daikin installer |
| 9 | PVC pipe | Delivery terms | Purchase Line | Delivery charged separately at PHP 1,500 |
| 10 | PVC pipe | Availability terms | Material | Immediate release from warehouse stock |
| 11 | PVC pipe | Condition or exclusion | Purchase Line | Returns only for unopened and undamaged bundles within seven days |
| 12 | Site cleanup | Condition or exclusion | Service | Hazardous-waste hauling and disposal excluded |
| 13 | Site cleanup | Availability terms | Service | Cleanup crew available on weekdays only |
| 14 | Grout | Condition or exclusion | Material | Store bags in a dry covered area |
| 15 | Grout | Availability terms | Material | Same-day pickup |

Each proposal has an exact source excerpt and verified character range within its candidate's primary or supporting spans. Coherent clauses with the same type and target remain one annotation; target changes produce distinct annotations.

## Required Exclusions

The following workflow, payment-status, and placeholder text creates neither Purchase Lines nor Evidence Annotations:

- Invoice marked paid
- `For approval`
- Follow up with Mario
- Receiving copy checked by Liza
- Send the accounting copy next week
- Payment status settled
- `For closeout approval`
- Supplier field left `TBD`

## Pass Conditions

- The primary profile completes with exactly one GPT-5.5 call and no retry.
- Strict field-level comparison passes; raw JSON property order, generated runtime IDs, timestamps, request metadata, and equivalent decimal serialization do not affect the result.
- Exactly four Purchase Lines in source order.
- Shapes are Bundled, Material, Service, Material.
- Every linked concept and External or Internal Provider classification has exact observed source text.
- Provider States and null-name invariants are correct.
- Exactly seven valid category paths.
- Exactly 15 annotations with the required types and targets.
- Zero valid annotation omissions and zero workflow-noise annotations.
- Zero concepts, Providers, or annotations grounded only in Project Memory.
- No partial Review Batch is accepted after an unrepaired validation failure.

## Promotion Gate

- This mixed-baseline fixture passes every condition above in two independent retry-disabled attempts within the same 10-call promotion run.
- The other sentinel fixture is the multi-concept installation bundle; the remaining six fixtures each pass once.
- All 10 attempts use the same pinned model snapshot, prompt/schema version, prompt-template hash, and schema hash; repeated fixtures retain the same rendered-input hash.
- No failed fixture or retry-assisted result is removed or replaced when determining the promotion result.
- An unscored infrastructure or configuration error makes the promotion run incomplete and requires the entire 10-call run to start again under a new run ID.
- No retry-enabled real-model run is required for promotion; any optional diagnostic is reported separately and cannot replace a failed primary-profile attempt.
- For the initial POC, observed latency, token usage, and estimated cost are reported but do not replace or add to the strict accuracy gate.
- The evaluator-generated promotion record contains this fixture's two qualifying outcomes and hashes and is checked in under `docs/evals/promotions/free-form/`.
- The fixture manifest contains complete human approval metadata for this exact golden result and version.
