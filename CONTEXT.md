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

**Source File**:
An original uploaded project document that acts as evidence for extracted knowledge. A source file may contain many candidate records and memory records.
_Avoid_: Memory record, item

**Source Submission**:
A project-scoped submitted source input, such as an uploaded file or manual source entry, that can be processed into reviewable candidates.
_Avoid_: Candidate batch, import request

**Manual Source Entry**:
A reviewer-entered source submission whose evidence content is typed or pasted rather than uploaded as a file.
_Avoid_: Lower-trust note, unsupported memory

**Processing Job**:
A durable record of Habi processing a source input, including its classification, progress, outcome, and review readiness.
_Avoid_: Background task, transient worker run

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
A required reviewer decision for AI-suggested taxonomy changes before affected records can be imported into project memory.
_Avoid_: Separate category import

**Taxonomy Decision**:
A retained project-scoped reviewer judgment on an AI-suggested category path, such as approving a new node, mapping it to an existing node, rejecting it, or deferring it.
_Avoid_: Candidate outcome, import decision

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
A previously imported memory record removed from active project-memory search while remaining preserved for history, evidence, and audit.
_Avoid_: Deleted record, deactivated record

**Purchase Line**:
A final/as-used project purchasing fact that connects an item or service to quantity, unit, price, supplier or provider, date, and source evidence when available.
_Avoid_: Bid estimate line, unselected canvass quote

**Unknown Field State**:
A reviewed data gap on a purchase line where a value such as unit, price, date, or provider is intentionally marked unknown instead of being invented or silently omitted.
_Avoid_: Null display fallback, missing bug

**Provider**:
An external company or person that supplied materials, provided services, or handled bundled supply-and-install work for the completed project.
_Avoid_: Separate supplier and service provider records for the same company

**Internal Provider**:
The contractor's own company, crew, or team providing a service or project resource instead of an external supplier or service provider.
_Avoid_: Unknown provider, supplier

**Provider Role**:
The role an external company or person played in a specific purchase line, such as material supplier, service provider, or supply-and-install provider.
_Avoid_: Separate duplicate provider

**Evidence Annotation**:
Typed supporting source text that qualifies a memory record but does not usually stand alone as reusable project memory.
_Avoid_: Note, miscellaneous memory record
