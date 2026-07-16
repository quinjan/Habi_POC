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
A candidate- and subject-specific reviewer decision between an AI-suggested category path and any Reviewer Taxonomy Draft. It must be explicitly accepted before the affected record can be imported into project memory.
Candidate Detail summarizes all active gates as `Needs decision` while any gate remains pending and as `Accepted` only after every active gate is accepted.
_Avoid_: Separate category import

**Taxonomy Decision**:
A retained project-scoped record of an explicitly accepted Taxonomy Gate, including its original AI path, accepted path, and accepted source. A later edit supersedes the decision but never deletes it from review history.
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

**Archived Memory Record**:
A previously imported memory record removed from active Project Memory browsing and search while remaining preserved for history, evidence, and audit.
_Avoid_: Deleted record, deactivated record

**Purchase Line**:
A final/as-used project purchasing fact that connects one or more Materials or Services to quantity, unit, price, supplier or provider, date, and source evidence when available.
_Avoid_: Bid estimate line, unselected canvass quote

**Purchase Line Concept Link**:
The association between one Purchase Line and one Material or Service Memory Record. A standard Purchase Line has one link; a Bundled Purchase Line has exactly two links: one Material and one Service.
_Avoid_: Duplicate purchase line, overloaded line type

**Bundled Purchase Line**:
A single Purchase Line whose source presents material supply and service work as one combined fact and price, while linking to exactly one Material and one Service. Each linked concept has its own reviewed name and Resolved Category Path.
_Avoid_: Artificially split material and service lines, separate provider record

**Unknown Field State**:
A reviewed data gap on a purchase line where a value such as unit, price, date, or provider is intentionally marked unknown instead of being invented or silently omitted.
_Avoid_: Null display fallback, missing bug

**Defaulted Field State**:
A review-visible value that Habi supplied from a project or POC default rather than directly extracting it from source evidence.
_Avoid_: Source-stated value, hidden assumption

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
An observed Material, Service, or supply-and-install role on a Purchase Line with an External or Internal Provider State. An external Provider's visible roles are derived from its active linked Purchase Lines, while Internal Provider roles remain visible only on the Purchase Line; a known Provider State on a Bundled Purchase Line automatically contributes all three roles, and an Unknown Provider has no role.
_Avoid_: Separate duplicate provider

**Evidence Annotation**:
Reviewer-approved typed supporting source text grounded in exactly one Evidence Record and qualifying exactly one Memory Record, but not usually standing alone as reusable Project Memory. Purchase Line is the default target for transaction terms; a linked Material, Service, or external Provider is targeted only when the source clearly qualifies that concept.
_Avoid_: Note, miscellaneous memory record

**Evidence Annotation Type**:
The reviewer-approved classification of an Evidence Annotation as delivery terms, payment terms, validity terms, warranty terms, availability terms, condition or exclusion, or general qualifier. General qualifier is used only when none of the specific types fits and the text still qualifies the purchasing fact or linked concept; workflow states, payment status, follow-up tasks, and other process noise are excluded.
_Avoid_: Free-form label, note category
