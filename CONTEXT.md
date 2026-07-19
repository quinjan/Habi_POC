# Habi

Habi is a private project purchasing intelligence product for construction teams. This context defines the product language used when discussing the POC and future product.

## Language

**Per-Project Memory Lab**:
A proof-of-concept workspace model where each completed construction project has its own reviewed, searchable project memory with source evidence.
_Avoid_: Cross-project search, multi-project recommendation engine

**Project Memory**:
Reviewed reusable knowledge extracted from a construction project's files, including materials, services, suppliers, prices, quantities, dates, and evidence.
_Avoid_: Archive, document dump

**Project Workspace**:
The container for one completed project's context, source submissions, review batches, taxonomy decisions, imported memory records, and per-project search.
_Avoid_: Global memory, company-wide search index

**Contractor Assigned**:
The Project Workspace text value naming the contractor responsible for the completed project. Habi supplies it as project-scoped extraction context to help resolve an Internal Provider State when a named provider matches after case-and-whitespace normalization; it is distinct from the client or owner. The legacy value `Internal` is a sentinel, not a contractor-name match.
_Avoid_: Client or owner, global company profile

**Source File**:
An original uploaded project document that acts as evidence for extracted knowledge. A source file may contain many candidate records and memory records.
_Avoid_: Memory record, item

**Source Submission**:
A project-scoped submitted source input, such as an uploaded file or manual source entry, that can be processed into reviewable candidates.
_Avoid_: Candidate batch, import request

**Evidence Record**:
A source-backed citation for one imported Purchase Line occurrence that points to one Source Submission and retains the strongest available locator and supporting content. It may support the Purchase Line and its linked Material, Service, and external Provider Memory Records.
_Avoid_: Source Submission, source file, annotation

**Manual Source Entry**:
A reviewer-entered source submission whose evidence content is typed or pasted rather than uploaded as a file.
_Avoid_: Lower-trust note, unsupported memory

**Processing Job**:
A durable record of Habi processing a source input, including its classification, progress, outcome, and review readiness.
_Avoid_: Background task, transient worker run

**AI Extraction**:
The AI-assisted conversion of preserved source content into validated extracted candidate proposals for reviewer approval. Active Project Memory from the selected Project Workspace may guide classification and matching, but it never replaces source evidence or reviewer approval.
_Avoid_: LLM process, direct memory writing

**Upload**:
The act of adding one source file to the project workspace so Habi can parse it and propose extracted candidates.
_Avoid_: Import

**Import**:
The reviewer-approved merge of extracted candidate records into active project memory.
_Avoid_: Upload, extraction

**Extracted Candidate**:
An AI-proposed record waiting for human review before it can become active project memory.
_Avoid_: Approved record, final record

**Rejected Candidate**:
An extracted candidate that the reviewer has explicitly excluded from import. In the POC, rejected and removed from import mean the same review outcome: visible in batch history, absent from active project memory.
_Avoid_: Separate removed-from-import status, deleted candidate

**Approved Candidate**:
An extracted candidate that the reviewer has explicitly included in import. In the POC, approved-as-is and edited-before-approval share the same review outcome; edits are tracked by comparing proposed and reviewed payloads.
_Avoid_: Separate edited decision, unreviewed approval

**Candidate Review Baseline**:
The initial candidate-local review state derived from the preserved AI proposal, validated Project Memory matches, and initial taxonomy-gate state when the Extracted Candidate enters review. A reviewer may restore this baseline before the Review Batch becomes terminal without changing immutable source provenance, batch-level relationships, candidate outcome, or audit history.
_Avoid_: Defaulted Field State, new AI extraction, batch reset

**Merged Candidate**:
An extracted candidate identified as a duplicate of another candidate in the same review batch. A merged candidate does not create its own import record; its include-or-exclude outcome follows its merge target until the reviewer unmerges it.
_Avoid_: Auto-deleted duplicate, implicit rejection

**Surviving Candidate**:
The candidate in a duplicate candidate group that carries the final reviewed payload when other candidates are merged into it. Only the surviving candidate can create or update an import record for that duplicate group.
_Avoid_: Group-level import payload, automatic winner

**Duplicate Candidate Group**:
A set of extracted candidates in the same review batch that appear to describe the same underlying project fact closely enough that importing them separately would create duplicate active project memory. AI may propose duplicate candidate groups, and reviewers may create or modify them during review.
_Avoid_: Arbitrary merge set, cross-batch duplicate group

**AI Confidence**:
Habi's estimate of how reliable an AI-proposed extraction, classification, or match is before human review. In the POC, confidence changes review friction but never replaces human approval.
_Avoid_: Approval, truth

**Taxonomy Gate**:
A candidate- and subject-specific reviewer decision required only for a new Material, Service, or external Provider between an AI-suggested category path and any Reviewer Taxonomy Draft. Selecting an existing Memory Record inherits its read-only Resolved Category Path and creates no gate; Candidate Detail shows `Needs decision` while any active new-record gate remains pending and `Accepted` when none remain pending.
_Avoid_: Separate category import

**Taxonomy Decision**:
A retained project-scoped record of an explicitly accepted new-record Taxonomy Gate, including its original AI path, accepted path, and accepted source. A later edit supersedes the decision but never deletes it from review history; inherited existing-record categories create no decision.
_Avoid_: Candidate outcome, import decision

**Reviewer Taxonomy Draft**:
A pending reviewer-proposed category path for one Taxonomy Gate that preserves its original AI suggestion. It may be copied only to matching pending gates, but each affected gate still requires its own explicit acceptance; it neither creates taxonomy nodes nor changes future defaults.
_Avoid_: Taxonomy Decision, bulk approval

**Top-Level Category**:
A broad taxonomy group used to organize project memory, such as Civil, Electrical, Plumbing, Services, or Suppliers/Providers.
_Avoid_: Subcategory

**Resolved Category Path**:
A complete approved taxonomy assignment required before a candidate can be imported into project memory. For the POC, this means the reviewer has selected or approved both the broad category and the specific subcategory needed for consistent learning.
_Avoid_: Uncategorized, top-level-only category

**Memory Record**:
A human-reviewed reusable fact extracted from a source file and made available for search.
_Avoid_: Candidate, document

**Proposed Project Memory Match**:
An AI-suggested association between one Extracted Candidate subject and one active Memory Record in the selected Project Workspace. It carries the exact Memory Record identity supplied to AI and remains distinct from source evidence and final import reuse.
_Avoid_: Source grounding, cross-project match, automatic import

**Memory-Aware Name**:
The reviewed Material, Service, or external Provider name selected through a searchable control that offers active same-type Project Memory records and permits a new free-text value. Selecting an existing option or typing its exact normalized name retains its Memory Record identity; only unmatched free text represents a new record.
_Avoid_: Plain text-only name, closed dropdown, implicit fuzzy match

**Archived Memory Record**:
A previously imported memory record removed from active Project Memory browsing and search while remaining preserved for history, evidence, and audit.
_Avoid_: Deleted record, deactivated record

**Purchase Line**:
A final/as-used project purchasing fact with source support for at least one Material or Service and for its purchasing status. It may connect those concepts to quantity, unit, price, supplier or provider, date, and other source evidence when available; those commercial fields alone do not establish a Purchase Line.
_Avoid_: Bid estimate line, unselected canvass quote

**Purchase Line Evidence Span**:
An exact, source-ordered character range in a free-form Manual Source Entry that contains evidence for one plausible Purchase Line. AI emits the exact source excerpt with its candidate, while Habi derives and verifies the character range against the preserved source text before the candidate can enter review.
_Avoid_: Whole-entry evidence, AI-authored summary, unverified offset

**Purchase Line Supporting Span**:
An exact character range containing shared source context, such as a Provider heading or global purchasing qualifier, that supports one or more Purchase Line Evidence Spans without becoming a Purchase Line itself. Every fact that relies on shared context cites the supporting span that grounds it.
_Avoid_: Purchase Line, ungrounded context, whole-entry context

**Observed Name Text**:
The exact, read-only source text that supports the proposed or reviewed name of a linked Material or Service on an Extracted Candidate. It is displayed as provenance beside the editable candidate name and does not create a separate review decision or Taxonomy Gate.
_Avoid_: Alternate candidate name, normalized name, review gate

**Observed Provider Text**:
The exact, read-only source wording that supports an external Provider name or an Internal Provider State on an Extracted Candidate. It is displayed beside the editable external Provider name or the `Internal` state; an Unknown Provider has no observed provider text, and the provenance creates no separate review decision.
_Avoid_: Provider Memory Record name for Internal, editable source wording, review gate

**Purchase Line Concept Link**:
The association between one Purchase Line and one Material or Service Memory Record, including any source-stated quantity, unit, and component unit price specific to that concept within a bundle. A standard Purchase Line has one link; a Bundled Purchase Line has two or more distinct links in any Material and Service combination supported by the source.
_Avoid_: Duplicate purchase line, overloaded line type

**Bundled Purchase Line**:
A single Purchase Line whose source presents two or more Materials or Services from one shared Provider identity or state as one combined commercial fact, usually with a shared price. Each linked concept has its own reviewed name and Resolved Category Path; concept type alone does not imply how linked concepts relate.
_Avoid_: Artificially split combined purchase, composite concept name, separate provider record

**Bundle Quantity**:
An optional source-stated quantity and unit for the complete Bundled Purchase Line as a commercial package, such as `1 lot`. It is distinct from quantities stated for individual linked concepts and is never inferred from them.
_Avoid_: Sum of concept quantities, default quantity, per-concept quantity

**Installation Relationship**:
A source-grounded relationship inside one Bundled Purchase Line connecting one installation Service link to one or more Material links that the Service installs. It, rather than mere Material-and-Service co-occurrence, establishes the supply-and-install Provider Role.
_Avoid_: Generic mixed bundle, delivery term, inferred installation

**Unknown Field State**:
A reviewed data gap on a purchase line where a value such as unit, price, date, or provider is intentionally marked unknown instead of being invented or silently omitted.
_Avoid_: Null display fallback, missing bug

**Defaulted Field State**:
A review-visible value that Habi supplied from a project or POC default rather than directly extracting it from source evidence.
_Avoid_: Source-stated value, hidden assumption

**Calculated Field State**:
A review-visible value that Habi deterministically calculated from explicitly source-stated inputs, such as quantity multiplied by unit price. It preserves the grounded inputs and formula and is distinct from source-stated, defaulted, unknown, or AI-inferred values.
_Avoid_: AI estimate, hidden arithmetic, source-stated total

**Real-Model Evaluation**:
An explicit, human-approved test that makes one retry-disabled call to the pinned free-form OpenAI model through Habi's production Manual Source Entry and worker path. It remains separate from ordinary offline tests, requires fresh human approval before every paid call or rerun, and prints a short pull-request scorecard without recording credentials or raw model payloads.
_Avoid_: Unit test, implicit network test, automatic rerun, deployment trigger

**Output-Affecting Evaluation Change**:
A change capable of altering the rendered free-form OpenAI request, parsed response, production validation, or persisted candidate proposal. It requires one passing Real-Model Evaluation before a human decides whether to merge; unrelated, XLSX-only, documentation-only, and post-extraction UI changes do not.
_Avoid_: Every pull request, ordinary offline test change, styling update

**POC Evaluation Fixture**:
The single synthetic mixed completed-project source used for Habi's paid free-form evaluation. Its versioned manifest supplies the exact source, Contractor Assigned, Project Memory, taxonomy vocabulary, and Human-Approved Golden Result needed to create an isolated Project Workspace.
_Avoid_: Customer document, eight-fixture suite, mutable test database seed

**Evaluation Scorecard**:
The automated PASS-or-FAIL Markdown summary produced by one Real-Model Evaluation for posting to the relevant pull request. It names the PRD, fixture, model, approving human, model-call count, Purchase Line count, and exclusion result; the human still decides whether to merge.
_Avoid_: Promotion record, deployment approval, raw model response

**Human-Approved Golden Result**:
The human-approved expected subset of domain output scored by the POC Evaluation Fixture, with reviewer identity, date, fixture version, and rationale. It covers the scorecard's agreed essential fields rather than every persisted candidate field; a model may assist drafting but cannot automatically create, overwrite, approve, or snapshot-update it.
_Avoid_: Exhaustive production contract, recorded current output, model-as-judge expectation, unreviewed snapshot

**Provider**:
An external company or person that supplied materials, provided services, or handled bundled supply-and-install work for the completed project. A Provider has its own reviewer-selected Resolved Category Path and is not categorized by the Material or Service categories of a linked Purchase Line.
_Avoid_: Separate supplier and service provider records for the same company

**Provider State**:
The reviewed Purchase Line classification of its provider as external, internal, or unknown. Only an external Provider State may create or link to a Provider Memory Record.
_Avoid_: Inferring internal or unknown from a missing provider name

**Internal Provider**:
The contractor recorded as Contractor Assigned, its crew, or team providing a service or project resource instead of an external supplier or service provider. It displays simply as Internal, retains observed Provider Roles on the Purchase Line, and never creates a Provider Memory Record.
_Avoid_: Unknown provider, supplier

**Provider Role**:
An observed Material, Service, or supply-and-install role on a Purchase Line with an External or Internal Provider State. Material and Service roles derive from linked concept types, supply-and-install derives only from an Installation Relationship, external roles aggregate through active linked Purchase Lines, Internal roles remain line-local, and Unknown has no role.
_Avoid_: Separate duplicate provider

**Evidence Annotation**:
Reviewer-approved typed supporting source text grounded in exactly one Evidence Record and qualifying exactly one Memory Record; a shared source qualifier produces a separate annotation for every affected Purchase Line rather than standing alone as reusable Project Memory. Purchase Line is the default target for transaction terms; a linked Material, Service, or external Provider is targeted only when the source clearly qualifies that concept.
_Avoid_: Note, miscellaneous memory record

**Evidence Annotation Type**:
The reviewer-approved classification of an Evidence Annotation as delivery terms, payment terms, validity terms, warranty terms, availability terms, condition or exclusion, or general qualifier. General qualifier is used only when none of the specific types fits and the text still has one clear target; workflow noise and qualifiers whose target cannot be determined are excluded.
_Avoid_: Free-form label, note category
