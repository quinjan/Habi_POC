# Habi Per-Project Memory Lab POC PRD

## Problem Statement

Small to medium construction teams often finish projects with valuable purchasing knowledge scattered across Excel files, PDFs, receipts, invoices, quotes used as final records, BOQs, notes, scans, images, and personal memory. When the next project comes along, the team has difficulty finding what was actually purchased, who provided it, what it cost, what quantities or units were used, and which source proves it.

The POC must prove that Habi can turn messy completed-project purchasing records into reviewed, searchable per-project memory. The proof is not a recommendation engine yet. The proof is whether a reviewer can submit sources for a completed project, review AI-proposed candidates, import approved records into project memory, and later ask evidence-backed search questions within that selected project.

## Solution

Build a Per-Project Memory Lab POC for multiple completed project workspaces. Each project workspace is isolated: project context, source submissions, taxonomy decisions, memory records, review batches, and search results do not cross project boundaries.

Inside a selected project, the reviewer can upload one file at a time or create one manual source entry. Habi processes the source input, proposes extracted candidates, and sends those candidates into review. The reviewer approves, edits, rejects, merges, resolves taxonomy gates, and imports only fully reviewed records. Active imported memory can then be browsed through Purchase Lines, inspected through Materials, Services, and Providers lists, and searched through a natural-language Search tab that returns prose answers plus cited evidence blocks.

The POC assumes every project workspace represents an already-completed project. Uploaded quotes, BOQs, invoices, receipts, and manual entries are interpreted as final/as-used project purchasing evidence, not as bid-stage or quote-comparison lifecycle data.

## User Stories

1. As a reviewer, I want to see a simple list of project names, so that I can choose which completed project memory to work on.
2. As a reviewer, I want to create a completed project workspace with basic context, so that each project memory has a clear frame.
3. As a reviewer, I want project context to include project name, project type, location, and completion date or year, so that records are grounded in the completed project.
4. As a reviewer, I want optional project context such as floor area, trade scopes, client or owner, and notes, so that I can add useful project background without over-modeling.
5. As a reviewer, I want each source submission to belong to exactly one project, so that project memories do not mix.
6. As a reviewer, I want search to run only inside the selected project, so that answers are based only on that project's approved memory.
7. As a reviewer, I want no cross-project search in the POC, so that sample projects remain isolated.
8. As a reviewer, I want no shared taxonomy learning across projects in the POC, so that one sample project's decisions do not affect another.
9. As a reviewer, I want the selected project to open on a Purchase Lines view, so that I can immediately inspect the central project purchasing facts.
10. As a reviewer, I want each purchase line row to show material or service, provider state, provider role, quantity, unit, price, date, category path, and evidence indicator, so that I can scan project memory quickly.
11. As a reviewer, I want to open a purchase line detail view, so that I can inspect linked material, service, provider, evidence annotations, source evidence, value history, and edit or archive actions.
12. As a reviewer, I want entry points for Materials, Services, and Providers, so that I can browse reusable entity memories created from imports.
13. As a reviewer, I want Providers to appear in one list with role filters, so that the same company is not duplicated as separate supplier and service-provider records.
14. As a reviewer, I want provider role filters such as material supplier, service provider, and supply-and-install provider, so that I can inspect how providers participated in the project.
15. As a reviewer, I want internal and unknown providers to remain purchase-line states, so that they do not become fake provider records.
16. As a reviewer, I want an Upload / Review tab, so that I can upload one file, add one manual source entry, start a new batch, or continue reviewing an ongoing batch.
17. As a reviewer, I want one file per upload, so that each source batch is easy to review and score.
18. As a reviewer, I want no bulk upload in the POC, so that review quality stays central.
19. As a reviewer, I want to create one manual source entry per submission, so that final/as-used facts can be entered when they are not available as files.
20. As a reviewer, I want manual source entries to support free-form text, so that I can paste or type source content.
21. As a reviewer, I want manual source entries to support simple structured rows, so that I can enter known purchase-line fields efficiently.
22. As a reviewer, I want structured manual rows to still go through normalization and categorization, so that manually entered facts follow the same import discipline as uploaded files.
23. As a reviewer, I want original uploaded source files to be preserved unchanged, so that evidence remains inspectable.
24. As a reviewer, I want extracted text, tables, and OCR output stored as derived artifacts, so that parser outputs can support review without replacing the original source.
25. As a reviewer, I want duplicate uploads or source submissions to warn but allow continuation, so that I can intentionally resubmit a source when parsing behavior improves.
26. As a reviewer, I do not want a direct reprocess feature in the POC, so that improved parsing can be tested through normal resubmission instead.
27. As a reviewer, I want unsupported file types to be marked unsupported, so that failures are clear.
28. As a reviewer, I want OCR or parsing failures to show failed status, so that I can decide whether to retry through a new submission or use manual entry.
29. As a reviewer, I want empty extraction to be marked as no candidates found, so that it is not confused with successful import.
30. As a reviewer, I want Habi to classify the source input type, so that processing and review can adapt to Excel, PDF, receipt, invoice, quote, BOQ, image, manual entry, or unknown inputs.
31. As a reviewer, I want Habi to create extracted candidates from each source input, so that AI output is staged before it becomes memory.
32. As a reviewer, I want extracted candidates to include raw extracted text, proposed fields, record type, category, subcategory, confidence, and evidence, so that I can review with enough context.
33. As a reviewer, I want candidates to remain outside active memory until approved and imported, so that AI proposals are not treated as project truth.
34. As a reviewer, I want to approve, edit, reject, merge, or remove candidates from import, so that each candidate receives an explicit review action.
35. As a reviewer, I want a batch to be done only after every candidate has an action, so that pending candidates do not leak into memory.
36. As a reviewer, I want to pause and resume batch review, so that I can handle realistic review sessions.
37. As a reviewer, I want batch statuses such as review pending, review in progress, ready to import, imported, and review closed with no import, so that I understand the batch lifecycle.
38. As a reviewer, I want import to happen only after approved records in a batch are ready, so that upload and import remain distinct events.
39. As a reviewer, I want successful import to mean approved records were merged into active project memory, so that processing success is not confused with memory creation.
40. As a reviewer, I want rejected candidates preserved for history and manual scorecard analysis, so that extraction failures can be studied.
41. As a reviewer, I do not want rejected candidates in normal memory search, so that search only uses approved active memory.
42. As a reviewer, I want AI to suggest likely duplicate candidates or matches to existing memory records, so that review is faster.
43. As a reviewer, I want all merges to require human approval, so that AI does not combine records incorrectly.
44. As a reviewer, I want merged candidates to count as resolved only when the final merged record is importable, so that batches cannot complete with unresolved merged records.
45. As a reviewer, I want AI confidence to change review friction but never replace approval, so that high-confidence candidates can be quick-reviewed without bypassing human judgment.
46. As a reviewer, I want low-confidence candidates visibly flagged, so that uncertain AI output gets careful attention.
47. As a reviewer, I want every imported memory record to have source evidence, so that every record can be trusted.
48. As a reviewer, I want candidates without source evidence to be unimportable, so that memory records are not unsupported claims.
49. As a reviewer, I want source evidence to include the original source and strongest available locator, so that I can inspect where a fact came from.
50. As a reviewer, I want spreadsheet evidence to include sheet and row when available, so that tabular records are easy to verify.
51. As a reviewer, I want PDF evidence to include page and snippet when available, so that document records are easy to verify.
52. As a reviewer, I want scan/image evidence to include OCR region or image reference when available, so that visual sources remain traceable.
53. As a reviewer, I want manual source entries to preserve entered text and metadata as evidence, so that manually submitted facts still have an evidence basis.
54. As a reviewer, I want source evidence to be inspectable from purchase lines and search evidence blocks, so that search answers are auditable.
55. As a reviewer, I want memory record types to include Material, Service, Provider, and Purchase Line, so that project memory is organized around useful construction purchasing concepts.
56. As a reviewer, I want Purchase Line to be the central project-specific memory fact, so that Habi can answer what was purchased or availed, from whom, at what quantity, unit, price, date, and evidence.
57. As a reviewer, I want Materials and Services to remain separate concepts, so that physical items and availed work are reviewed and searched in contractor-native language.
58. As a reviewer, I want Providers to represent external companies or people, so that suppliers and service providers are not duplicated when the same company plays multiple roles.
59. As a reviewer, I want one provider to support multiple observed roles, so that a company can be material supplier, service provider, or supply-and-install provider across different purchase lines.
60. As a reviewer, I want provider records to require a resolved category path, so that provider memories are organized consistently.
61. As a reviewer, I want provider roles to remain searchable, so that I can answer capability questions.
62. As a reviewer, I want every purchase line to link to at least one Material or Service, so that purchase lines do not become miscellaneous junk records.
63. As a reviewer, I want miscellaneous-looking charges to be classified as material or service concepts, so that mobilization, consumables, delivery, and similar charges remain searchable.
64. As a reviewer, I want bundled material/service lines to remain bundled when the source presents them as one combined fact, so that combined supply-and-install prices are not split artificially.
65. As a reviewer, I want bundled lines to link to multiple memory records when needed, so that a line can connect both product and service concepts.
66. As a reviewer, I want bundled provider capabilities to be searchable, so that I can ask which company supplied and installed a product.
67. As a reviewer, I want purchase lines to track provider type as external, internal, or unknown, so that self-performed work and missing provider data are not confused.
68. As a reviewer, I want internal provider to mean the contractor's own company, crew, or team, so that self-mobilization and own-worker services are represented clearly.
69. As a reviewer, I want internal provider to remain a purchase-line state, not a provider memory record, so that the POC does not create unnecessary internal company profiles.
70. As a reviewer, I want unknown provider to be allowed but visible as a data gap, so that useful records can import even when supplier/provider is missing.
71. As a reviewer, I want generic notes to avoid becoming normal memory records, so that project memory stays clean.
72. As a reviewer, I want note-like text to become evidence annotations or structured attributes when relevant, so that terms like delivery included or payment terms qualify the right record.
73. As a reviewer, I want workflow noise like for approval or paid already to stay out of memory unless later brought into scope, so that the POC remains focused.
74. As a reviewer, I want evidence annotation types such as delivery terms, payment terms, validity terms, warranty terms, availability terms, condition or exclusion, and general qualifier, so that supporting text is typed without becoming standalone memory.
75. As a reviewer, I want AI to suggest top-level categories and subcategories, so that I do not need to pre-model all construction data before using Habi.
76. As a reviewer, I want AI-suggested taxonomy changes to require taxonomy gates, so that category growth stays human-controlled.
77. As a reviewer, I want top-level category suggestions to require stronger confirmation than subcategories, so that broad taxonomy changes are not created accidentally.
78. As a reviewer, I want every imported record to have a resolved category path, so that active memory has consistent learning patterns.
79. As a reviewer, I do not want top-level-only categorization to be importable, so that records have both broad and specific taxonomy placement.
80. As a reviewer, I want uncategorized candidates to require selecting an existing taxonomy node, approving a new node, or removing the candidate from import, so that no uncategorized memory enters active search.
81. As a reviewer, I want taxonomy decisions to persist within the project, so that later uploads in the same project benefit from earlier review decisions.
82. As a reviewer, I want taxonomy learning not to cross projects in the POC, so that sample projects remain isolated.
83. As a reviewer, I want Habi to retain approved, mapped, rejected, and deferred taxonomy decisions for analysis, so that the manual scorecard can identify taxonomy issues.
84. As a reviewer, I want only approved and mapped taxonomy decisions to affect future default categorization, so that uncertain or rejected suggestions do not pollute the project.
85. As a reviewer, I want taxonomy nodes to be editable or renameable within a project, so that early naming mistakes can be corrected.
86. As a reviewer, I do not need a taxonomy or entity alias system in the POC, so that scope stays tight.
87. As a reviewer, I want search to use currently visible record text and source/evidence text, so that behavior stays understandable.
88. As a reviewer, I want units normalized when present, so that purchase lines can be searched and compared.
89. As a reviewer, I want to confirm, edit, or add units during review, so that AI unit extraction can be corrected.
90. As a reviewer, I want unit_unknown to be visible when the source has quantity but unclear unit, so that missing data is explicit.
91. As a reviewer, I do not want Habi to invent quantity or unit when absent, so that records avoid fake precision.
92. As a reviewer, I want prices normalized when present, so that purchase lines support search and simple analytics.
93. As a reviewer, I want currency to default to PHP unless the source says otherwise, so that Philippine project records are efficient to review.
94. As a reviewer, I want calculated unit price suggestions to require confirmation, so that derived values are not silently trusted.
95. As a reviewer, I want price_unknown to be visible when price is missing, so that missing data is explicit.
96. As a reviewer, I want dates normalized when present, so that queries like last July can work when supported by data.
97. As a reviewer, I want multiple detected dates to be reviewed for relevance, so that invoice date, purchase date, delivery date, and other dates are not confused.
98. As a reviewer, I want date_unknown to be visible when date is missing, so that search can explain limitations.
99. As a reviewer, I want imported records to be editable after import, so that review mistakes can be corrected.
100. As a reviewer, I want post-import edits to preserve history, so that memory changes do not silently overwrite prior reviewed values.
101. As a reviewer, I want latest reviewed values to be active, so that current project memory reflects the latest approved correction.
102. As a reviewer, I want records to be archived rather than deleted, so that removed records remain available for history, evidence, audit, and possible restoration.
103. As a reviewer, I want archived records excluded from normal project-record search, so that active memory search is clean.
104. As a reviewer, I want archived records visible from source-input and history views, so that provenance remains complete.
105. As a reviewer, I do not need archive reason to be required in the POC, so that archiving remains lightweight.
106. As a reviewer, I want a Search tab with a natural-language input and large rich-text AI response area, so that I can ask project-memory questions conversationally.
107. As a reviewer, I want search answers to include prose plus cited evidence blocks, so that answers are readable and auditable.
108. As a reviewer, I want evidence blocks to show matched purchase lines or entity records, provider, quantity, price, date, source reference, and why it matched when available, so that I can verify the answer.
109. As a reviewer, I want search to distinguish exact match, related match, and no reviewed memory found, so that fuzzy search does not overclaim.
110. As a reviewer, I want broad queries like Pipe to return grouped related results, so that broad exploration stays useful.
111. As a reviewer, I want specific queries to prefer exact matches first, so that precise questions get precise answers.
112. As a reviewer, I want ambiguous queries to ask for clarification only when results are too mixed, so that search remains helpful without being evasive.
113. As a reviewer, I want search to support material and service names, categories, subcategories, providers, prices, quantities, units, specs, dates, and evidence annotations, so that project memory can be explored flexibly.
114. As a reviewer, I want search to answer questions like who supplied PVC pipes, which company supplied and installed PVC pipe, show hauling services, get purchased concrete coring last July, and where did this supplier appear, so that common construction purchasing questions are covered.
115. As a reviewer, I want search to answer simple per-project analytics only when data supports it, so that counts and totals are useful but not misleading.
116. As a reviewer, I want analytics responses to state which records were excluded because fields were missing, so that totals are not treated as accounting-grade claims.
117. As a reviewer, I want no central company-wide search in the POC, so that search remains scoped to the selected project.
118. As a reviewer, I want no recommendation starter packs in the POC, so that the product proof stays focused on reviewed memory.
119. As a reviewer, I want manual scorecard evaluation outside the app, so that the POC can be judged without building extra analytics UI.
120. As a reviewer, I want the manual scorecard to measure parsing, extraction, normalization, review, search, evidence, data readiness, and recommendation readiness, so that the POC teaches what must improve before MVP.

## Implementation Decisions

- Build a small end-to-end app experience centered on selected project workspaces, not a central dashboard.
- Omit authentication, teams, permissions, and user management for the local single-user POC.
- Keep the React/Vite frontend and FastAPI backend separate. The frontend communicates with the backend only through API contracts and remains a light UI for project selection, source submission, review, browsing, and search.
- The backend owns all project-memory rules, API validation, job processing, AI calls, database access, file/artifact access, import semantics, and retrieval behavior.
- FastAPI Pydantic request and response models should generate the OpenAPI contract, and the React frontend should use generated or shared TypeScript client types from that contract.
- The FastAPI backend should be a modular monolith with clear backend modules rather than split into separate services for the POC.
- The backend should use SQLAlchemy for Postgres persistence and Alembic for schema migrations.
- Keep the project list as a simple project-name selector.
- Keep all project context, source submissions, review batches, taxonomy decisions, imported memory records, and search scoped to the selected project.
- Enforce project scoping in the backend and database through query scoping, required parent relationships, and foreign keys; do not rely on frontend filtering for project isolation.
- Do not share taxonomy learning, memory records, evidence, or search results across projects in the POC.
- Treat each project workspace as already completed; uploaded sources are final/as-used evidence for that project.
- Keep bid baseline, award baseline, quote comparison, canvassing alternatives, change events, issue history, payment status, and lessons learned outside the POC.
- Use Purchase Lines as the default selected-project view and central memory fact.
- Add secondary entity-list entry points for Materials, Services, and Providers.
- Model Provider as one external provider entity with observed roles rather than separate Supplier and Service Provider records for the same company.
- Treat internal provider and unknown provider as purchase-line states, not Provider memory records.
- Treat Manual Source Entry as a source input that follows the same candidate review and import workflow as uploaded files.
- Preserve original uploaded files unchanged.
- Store extracted text, tables, OCR output, and manual-entered source text as evidence artifacts tied to source inputs.
- Uploads and manual source submissions should return source submission and processing job IDs quickly. The frontend reads job and batch status through the backend API while parsing, OCR, AI extraction, embeddings, and review preparation run in the backend job pipeline.
- Do not support direct reprocessing in the POC; resubmission creates a new source input.
- Warn but allow duplicate source submissions.
- Keep source submission and import as distinct product events.
- Make import successful only when at least one reviewer-approved record is merged into active project memory.
- Require every candidate in a batch to have a review action before the batch can be imported or closed.
- Support paused/resumed review batches.
- Use batch statuses: review pending, review in progress, ready to import, imported, and review closed with no import.
- Preserve rejected candidates for batch history and manual scorecard analysis, but exclude them from normal memory search.
- Require human approval for candidate merges.
- Make merge resolution valid only when the final merged record is importable.
- Let AI confidence influence review friction but never bypass human approval.
- Require source evidence for every imported memory record.
- Require a resolved category path for every imported memory record.
- Require every imported purchase line to link to at least one Material or Service memory record.
- Allow purchase lines to link to Providers when known, but allow unknown provider as a visible data gap.
- Allow purchase lines to use provider_type values of external, internal, and unknown.
- Preserve bundled material/service purchase lines when the source presents them as one combined fact.
- Support evidence annotations as typed supporting source text attached to memory records, not as standalone generic notes.
- Seed evidence annotation types: delivery terms, payment terms, validity terms, warranty terms, availability terms, condition or exclusion, and general qualifier.
- Let AI suggest new top-level categories and subcategories, but require taxonomy gates.
- Require stronger confirmation for new top-level categories than for subcategories.
- Keep taxonomy decisions project-scoped.
- Allow taxonomy nodes and records to be edited in the selected project.
- Do not implement alias behavior for taxonomy or entity records in the POC.
- Normalize units, prices, and dates when present, but keep unknown/missing values visible rather than inventing them.
- Allow reviewer confirmation, edits, and additions for units and derived price values.
- Preserve value history for post-import edits and later approved imports.
- Archive memory records rather than deleting them.
- Exclude archived records from normal project-memory search by default.
- Keep archived records visible in source-input and history views.
- Make archive reason optional for the POC.
- Search only active imported memory in the selected project.
- Search should return rich-text answers with cited evidence blocks.
- Search should label exact matches, related matches, and no reviewed memory found.
- Search should support broad grouped queries and simple per-project analytics only when structured data supports them.
- Do not build an in-app scorecard module for the POC; keep scorecard evaluation manual.

Proposed backend modules:

- Project Workspace module: owns project creation, project selection, project context, and project-scoped isolation.
- Source Submission module: owns one-file uploads, manual source entries, duplicate warning, source preservation, and source-input metadata.
- Processing module: owns file/manual-entry classification, parsing, OCR/table extraction coordination, derived artifacts, processing statuses, error states, and job-status APIs for frontend polling or refresh.
- AI Extraction and Normalization module: owns candidate proposal, record type suggestion, normalization, taxonomy suggestion, confidence, evidence references, duplicate suggestions, and provider-role suggestions. Extracted candidates should use one canonical candidate envelope with validated type-specific payloads for Materials, Services, Providers, and Purchase Lines.
- Review Batch module: owns candidate decisions, paused/resumed review, merge review, taxonomy gates, batch status transitions, and readiness for import.
- Import module: owns merging approved candidates into active project memory, latest-approved-wins behavior, source evidence requirements, resolved category path requirements, and successful-import semantics.
- Taxonomy module: owns project-scoped taxonomy nodes, taxonomy gates, edits/renames, mapped/rejected/deferred decisions, and project-scoped learning.
- Memory Store module: owns Materials, Services, Providers, Purchase Lines, links between records, provider roles, provider type, evidence annotations, value history, active/archive state, and edit history. Imported memory should use a shared memory-record backbone for common fields plus type-specific tables for Material, Service, Provider, and Purchase Line behavior.
- Evidence module: owns source evidence links, evidence snippets, evidence locators, evidence inspection, original source preservation, and manual source entry evidence. Evidence snippets and evidence links should be generated before review and attached to candidates; import promotes approved candidate evidence into memory-record evidence. Evidence is required for every imported memory record but should be modeled as linked evidence records rather than inline memory-record fields.
- Search/Retrieval module: owns selected-project retrieval, hybrid structured/semantic matching, memory-record and evidence-snippet embeddings, two-stage retrieval and reranking, rich-text answer generation, evidence/result blocks, exact/related/no-result labeling, broad query grouping, and simple analytics with missing-data caveats. Normal Search should use active approved memory only; source/history inspection and analytics should use deliberate separate retrieval modes.
- Manual Scorecard process: not an app module; a manual assessment artifact using exported observations or direct review. Golden search questions are user-owned evaluator files or notes outside the app; the POC should not import or model them as application data.

The backend should use Python with FastAPI because it owns parsing, OCR coordination, AI extraction, schema validation, embeddings, job processing, import rules, retrieval, database access, and file/artifact access. The frontend should use React with Vite and remain lightweight, separate, and API-only.

API contracts should be OpenAPI-first from FastAPI. Frontend request and response types should be generated or shared from that contract rather than manually maintained.

The initial API surface should be workflow-shaped rather than table-shaped. The frontend should call backend actions such as creating projects, submitting sources, reading processing status, reviewing candidates, importing batches, browsing active memory, inspecting evidence, and searching selected-project memory. The frontend should not assemble domain rules from generic table CRUD endpoints.

Persistence should use SQLAlchemy and Alembic so the Postgres schema, pgvector index, review/import tables, evidence links, and type-specific memory tables can evolve with explicit migrations.

## Testing Decisions

Good tests for this POC should verify externally visible behavior rather than implementation details. The strongest tests will use realistic source inputs, candidate records, review decisions, imported memory records, and natural-language search questions. Tests should confirm that Habi preserves trust boundaries: candidates do not appear in active search, imports require review, records require evidence and resolved category paths, archived records are excluded from normal search, and project isolation is maintained.

Modules that should be tested:

- Project Workspace module: project context creation, project selection, and project-scoped isolation.
- Source Submission module: one-file upload rule, manual source entry rule, duplicate warning behavior, and original source preservation metadata.
- Processing module: supported/unsupported source states, parsing failure, empty extraction, and processing status transitions.
- Review Batch module: candidate decision completeness, pause/resume behavior, batch status transitions, merge resolution, and ready-to-import gating.
- Import module: successful import semantics, evidence requirement, resolved category path requirement, purchase-line link requirement, latest-approved-wins behavior, and rejection exclusion.
- Taxonomy module: taxonomy gates, top-level vs subcategory confirmation, project-scoped taxonomy learning, taxonomy edits, and no cross-project leakage.
- Memory Store module: purchase-line links to Material/Service/Provider, provider roles, provider_type behavior, bundled line behavior, evidence annotations, edits with value history, and archive behavior.
- Evidence module: evidence locator storage, source inspection links, manual source entry evidence, and no-evidence-no-import enforcement.
- Search/Retrieval module: active-only search, archived exclusion, project-scoped search, two-stage retrieval behavior, exact/related/no-result labeling, broad query grouping, evidence blocks, and supported simple analytics with missing-data warnings.

Example behavior-level test scenarios:

- A pending candidate batch does not affect project-memory search.
- A batch cannot become ready to import while any candidate lacks a review action.
- A candidate with unresolved taxonomy cannot be imported.
- A candidate without source evidence cannot be imported.
- A purchase line without a linked Material or Service cannot be imported.
- A purchase line with unknown provider can be imported and marked as a data gap.
- A self-mobilization service imports with provider_type internal and no Provider memory record.
- A bundled supply-and-install line remains one purchase line linked to both Material and Service.
- A provider appearing as supplier in one line and service provider in another remains one Provider record with multiple roles.
- A rejected candidate is visible in batch history but absent from normal search.
- An archived record is absent from normal search but visible from source/history views.
- A broad search for Pipe returns grouped related results rather than pretending to be an exact item query.
- A query for total PVC pipe spend sums only records with normalized prices and reports excluded records with missing prices.
- Project A search does not return Project B memory, taxonomy, source evidence, or candidates.

Manual POC scorecard dimensions:

- Parsing coverage: how many useful rows/items were extracted from each file?
- Extraction accuracy: how many candidate fields were correct before human edits?
- Normalization accuracy: how often AI proposed the right type, normalized name, category, and subcategory?
- Review efficiency: how many candidates were approved as-is, edited, rejected, or merged?
- Taxonomy learning: whether approved project-scoped taxonomy nodes and mappings reduce categorization effort in later uploads for the same project.
- Search relevance: how many golden questions returned the expected record and evidence?
- Evidence quality: how often results linked back to usable source evidence?
- Data readiness: which fields and file types were useful, missing, noisy, or unreliable?
- Recommendation readiness: whether the resulting memory seems strong enough to support a future starter-pack feature.

Suggested early POC targets:

- At least 70% of useful candidates are extracted from structured Excel/PDF tables.
- At least 60% of candidates are approved or lightly edited rather than rejected.
- At least 70% of golden search questions return correct or partially correct results.
- Every approved memory record has at least one source evidence link.
- The scorecard identifies top data gaps before MVP.

## Out of Scope

- Cross-project search.
- Cross-project taxonomy learning.
- Shared company-level taxonomy.
- Multi-project similarity search.
- Central company-wide memory search.
- Recommendation starter packs.
- Any generated recommendation pack for a new project.
- Importing a new project for recommendation testing.
- Bid baseline workflows.
- Award baseline workflows.
- Canvassing alternatives and quote-comparison workflows.
- Project lifecycle tracking from bidding through closeout.
- Change event logging.
- Active project issue tracking.
- Payment status tracking.
- Accounting-grade financial reporting.
- ERP behavior.
- Inventory behavior.
- Scheduling behavior.
- Supplier marketplace behavior.
- Autonomous final engineering or purchasing decisions.
- Bulk upload.
- Direct source reprocessing.
- In-app scorecard dashboard/module.
- Taxonomy or entity alias system.
- Manual records without source-entry evidence.

## Further Notes

The POC should preserve the product principle that Habi helps users avoid pre-modeling messy construction data while still keeping active memory trustworthy. AI may propose categories, subcategories, normalized names, attributes, links, confidence, and duplicate matches, but human review determines what becomes active project memory.

The POC should treat all uploaded and manually entered source inputs as final/as-used project evidence because each project workspace represents a completed project. The MVP can later introduce lifecycle stages, quote comparison, cross-project learning, central search, and recommendation workflows.

The existing design spec remains useful as the source design discussion. This PRD is the product-requirements artifact distilled from those decisions.
