# Use One GPT-5.5 Pass For Free-Form Extraction

> **Status:** The production extraction decision remains accepted. Its model and reasoning defaults are superseded by ADR 0153; its eight-fixture, ten-call evaluation and promotion-record clauses are superseded by ADR 0151.

Free-form Manual Source Entry AI Extraction will use one GPT-5.5 request as its default happy path. The request receives the preserved source, Contractor Assigned, bounded Project Memory from only the selected Project Workspace, taxonomy context, the seven Evidence Annotation Type definitions, and the complete structured candidate contract; it returns source-ordered Purchase Line candidates together with exact primary and supporting excerpts, Observed Name Text for grounded linked concepts, Observed Provider Text for External or Internal Provider States, taxonomy suggestions, and grounded annotation proposals. Habi derives and verifies every character range, requires candidate facts to cite that candidate's verified spans, and enforces Purchase Line shape, Provider State, taxonomy, annotation, and workflow-noise invariants before review. A structurally invalid result retries the whole request once, while a failure isolated to one otherwise grounded candidate may use a targeted repair request; both retry paths use the same pinned GPT-5.5 snapshot at `xhigh` reasoning rather than switching models. The normal successful path therefore remains one model call.

After the permitted repair, any remaining invalid detected candidate fails the complete free-form Processing Job under ADR 0124 rather than producing a partial Review Batch.

This supersedes ADR 0120's separate source-only segmentation call while retaining its source-span vocabulary, recall bias, exact backend grounding authority, and atomic handling of invalid source structure. It supersedes ADR 0078's nano-first policy only for free-form Manual Source Entries: `OPENAI_FREE_FORM_MODEL` defaults to the pinned `gpt-5.5-2026-04-23` snapshot for reproducible regression scores, `OPENAI_FREE_FORM_REASONING_EFFORT` defaults to `high` for the accuracy-first POC, `OPENAI_FREE_FORM_RETRY_REASONING_EFFORT` defaults to `xhigh`, and the centralized `OPENAI_FREE_FORM_RETRIES_ENABLED` flag defaults to `true`, with all settings remaining deployment-overridable. Retry behavior follows ADR 0127. XLSX processing stays on the existing independently configured `OPENAI_MODEL` and is not changed by this decision. The separation keeps free-form semantic accuracy and XLSX profiling, deterministic row grounding, chunking, cost, and model evaluation as distinct deployment concerns.

The free-form GPT-5.5 system prompt must define all seven Evidence Annotation Types and their targeting rules, require separate proposals for distinct qualifying clauses, and require a shared qualifier to be proposed independently on every Purchase Line it clearly qualifies. It must also explicitly exclude workflow states, payment status, follow-up tasks, and other process noise. The real-model regression scorecard verifies these behaviors; model capability is not treated as an implicit substitute for the prompt contract.

Annotation granularity follows ADR 0150: coherent clauses with the same type and target remain one proposal, while type or target changes require separate proposals.

Annotation targeting follows ADR 0134: GPT-5.5 must omit qualifiers whose target cannot be determined and must never use an ambiguous qualifier to create a Purchase Line.

Free-form annotation validation follows ADR 0133: there is no 20-item cap or silent dropping, and annotation failures use the same repair and atomic-failure policy as other candidate invariants.

Taxonomy suggestions use separate structured top-level and subcategory fields and follow ADR 0125; the prompt must not ask GPT-5.5 to return a combined category path.

Purchase Line shape and Installation Relationships follow ADR 0142: Habi derives standard versus bundled from grounded link count, the free-form schema contains no independent `line_type`, and supply-and-install requires an exact grounded relationship rather than concept-type co-occurrence.

Candidate creation follows ADR 0135 and requires source-grounded concept evidence plus final/as-used purchasing evidence; commercial fragments and annotations cannot create Purchase Lines.

Candidate-local non-final evidence follows ADR 0136 and overrides broader headings or memory context; the prompt must teach this through contextual examples rather than a keyword blacklist.

Coherent transaction and completed-work shorthand follows ADR 0137 and is presumed final/as-used unless the source provides contrary evidence.

Completed Service work versus planned or imperative activity follows ADR 0138 and must be inferred semantically from source context.

Service objects follow ADR 0139 and do not become Material links unless the source establishes supply or purchase in the same fact.

Incidental transaction terms follow ADR 0140 and remain annotations rather than becoming Service links unless the source presents a substantive purchased or completed Service.

Multiple Materials or Services presented as one combined commercial fact remain one multi-concept Bundled Purchase Line under ADR 0142.

Provider boundaries follow ADR 0144: one bundle has one shared Provider identity or state, and different Providers produce separate Purchase Lines with unallocated prices left Unknown.

The selected Project Workspace context follows ADR 0128: GPT-5.5 receives the complete active Project Memory vocabulary for free-form extraction, without ADR 0115's lexical filtering or record caps.

Proposed Project Memory matches follow ADR 0129 and use explicit backend-validated record IDs rather than inferred name-only badges.

The primary real-model regression is an explicit opt-in OpenAI API evaluation suite. It loads `OPENAI_API_KEY` from the ignored repository-root `.env`, pins `gpt-5.5-2026-04-23` at `high` reasoning, and disables application and client-level retries. A qualifying promotion run contains exactly 10 scored calls under one configuration: every one of the eight fixtures once, followed by one repeat each of the mixed completed-project baseline and multi-concept installation bundle sentinels. All 10 must satisfy their scorecards. Every fixture is a checked-in, versioned manifest containing the exact source, Contractor Assigned, complete Project Memory, taxonomy vocabulary, and expected result. The evaluator seeds an isolated Project Workspace from the manifest, reads no ambient memory, and records the manifest content hash. It compares validated results through strict domain-field assertions, including exact names, links, categories, commercial values, annotations, excerpts, and ranges, while ignoring only documented serialization and runtime metadata such as object-property order, generated IDs, timestamps, request IDs, and equivalent decimal formatting. Any fixture or manifest change or scored model failure requires a new complete 10-call run. An API, configuration, or evaluator error that yields no scorable model response is retained as an unscored incomplete run, and the entire 10-call run starts again under a new run ID. A response that reaches validation is scored and cannot be discarded as infrastructure noise. Ordinary tests remain offline and credential-free. Retry-enabled real-model diagnostics are optional and never contribute to promotion; deterministic offline tests force every retry branch. Credentials are never emitted into logs or evaluation artifacts.

For the initial POC, strict semantic accuracy is the only hard promotion gate. Latency, token usage, and estimated API cost remain mandatory reported observations. The first qualifying 10-call run establishes p50/p95 latency and usage/cost baselines; any later hard operational threshold requires an explicit prospective decision and does not retroactively change that promotion result.

The real-model evaluator exercises the production free-form application path rather than invoking the OpenAI provider directly. It seeds an isolated Postgres Project Workspace from the manifest, submits the Manual Source Entry and queued `ai_manual_free_form_v1` Processing Job through the production boundary, runs the production worker and processor, and scores the terminal job plus persisted Review Batch, Extracted Candidates, proposed payloads, evidence, and diagnostics. It stops before reviewer edits or final import. Evaluation-specific prompts, schemas, grounding, or semantic validators are prohibited because they could drift from production behavior.

Each model attempt records human prompt and schema versions plus SHA-256 fingerprints of the actual production prompt template, fully rendered role-ordered model input, and canonical structured-output schema immediately before transport. Credentials and transport metadata are excluded. The rendered-input hash is fixture-specific; the template and schema hashes identify the shared request contract. Any output-affecting hash or request-parameter change defines a new evaluation configuration and requires a new qualifying 10-call run, even if a human-readable version was not bumped.

Promotion additionally requires an evaluator-generated, schema-validated JSON record checked in under `docs/evals/promotions/free-form/`. It contains the configuration and manifest hashes, the complete 10-attempt qualifying matrix with eight coverage calls and two sentinel repeats, safe aggregate metrics and pricing provenance, summaries of preceding unsuccessful attempts, and digests of sanitized verbose artifacts. Console output alone is not promotion evidence. Raw model requests, responses, and diffs remain outside Git in ignored local or access-controlled CI storage, and no credential or customer data enters either the record or artifacts.

The 10-call suite is explicitly invoked only for changes capable of altering free-form production output or its evaluation contract, including model/request parameters, prompts and context rendering, memory construction, schemas and parsing, grounding and semantic validation, calculations, annotations, pre-persistence processing, fixtures, comparator behavior, or relevant dependencies. It is not part of ordinary PR CI. Documentation-only, post-extraction UI, deterministic import, XLSX-only, and unrelated changes remain credential-free. A relevant change must carry a new qualifying Promotion Evidence Record before its free-form configuration is promotable; uncertain impact is treated as output-affecting.

The suite has exactly eight synthetic, non-customer fixtures: the existing mixed completed-project baseline and seven additional realistic multi-paragraph sources. Each additional fixture focuses on one required risk family but also includes natural cross-cutting headings, shorthand, qualifiers, commercial facts, Project Memory distractors, and workflow noise. Internal schema labels must not leak expected answers into the source. Minimal single-rule cases remain offline deterministic tests.

The suite does not prescribe a fixture length target or near-maximum source case. Realism is assessed through semantic coverage; source-length limits and boundaries remain deterministic application tests.

Every expected fixture result is a human-approved golden with reviewer identity, approval date, reviewed manifest version, and domain rationale. Models may assist drafting but cannot approve, overwrite, snapshot-update, or otherwise turn their current output into the expected answer. Any source, context, or golden change creates a new manifest version, requires renewed human approval, and requires a new qualifying 10-call promotion run.
