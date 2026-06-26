# Habi Single-Project Memory Lab POC Design

## Purpose

The Habi POC is a Single-Project Memory Lab for one already-completed construction project.

The POC should prove that Habi can take a messy completed project folder and turn it into a trustworthy, searchable private project memory. It should also reveal which data types, normalized fields, taxonomy decisions, and human review steps are necessary before building an MVP or pilot recommendation workflow.

The core proof is:

> Can Habi transform one messy completed project folder into reviewed memory that users can search semantically, with accurate records and source evidence?

## POC Approach

Use one completed project deeply instead of multiple projects shallowly.

The POC should focus on final/as-used project records. It should not attempt to reconstruct bid baseline, award baseline, change events, issue history, or lessons learned unless those details naturally appear in the imported files.

The POC will test:

- Whether mixed project files can be parsed into useful candidates.
- Whether AI can propose useful record types, categories, subcategories, normalized names, and attributes.
- Whether a human can efficiently approve or correct the AI output.
- Whether approved memory records are searchable with evidence-backed results.
- Whether the resulting memory is strong enough to support a future recommendation starter-pack feature.

## In Scope

- One completed project workspace.
- One file per upload.
- Mixed file types such as Excel, PDFs, receipts, quotes, invoices, BOQs, purchasing notes, scans/images, and similar records.
- AI parsing and extraction into staged candidates.
- Human review before data becomes active memory.
- Materials, services, suppliers, service providers, prices, quantities, units, dates, and source references when available.
- Seed taxonomy: Civil, Electrical, Plumbing, Services, Suppliers/Providers.
- AI-suggested new subcategories that require human approval.
- Latest approved import wins for active values.
- Value history and source evidence for traceability.
- Within-project semantic search and evidence retrieval.
- A POC scorecard for parsing, extraction, normalization, review, search, evidence, data readiness, and recommendation readiness.

## Out Of Scope

- Multi-project similarity search.
- Importing a new project for recommendation testing.
- Full recommendation starter packs.
- Bid baseline and award baseline workflows.
- Change event logging.
- Active project issue tracking.
- Lessons-learned capture unless imported naturally from source files.
- ERP, accounting, inventory, scheduling, or supplier marketplace behavior.
- Autonomous final engineering or purchasing decisions.

## Import And Review Workflow

1. User creates one completed project memory workspace.
2. User uploads one source file.
3. Habi creates one import job for that file.
4. Habi classifies the file type, such as Excel, PDF, receipt, invoice, quote, BOQ, note, image, or unknown.
5. Habi parses the file using the best available method for the format, such as spreadsheet parsing, PDF text extraction, table extraction, or OCR.
6. Habi uses AI to extract candidate records.
7. Each extracted candidate enters the review queue, not active memory.
8. Each candidate includes raw extracted text, proposed fields, suggested record type, category, subcategory, confidence, and source evidence.
9. Human reviewer approves, edits, rejects, merges, or requests re-parse.
10. Approved candidates become active memory records.
11. If an approved later import updates an existing value, latest approved import wins.
12. Previous values remain visible in value history and evidence history.
13. AI-suggested new subcategories must be approved or mapped to existing taxonomy nodes by a human reviewer.

## Data Model

### Project

One completed project memory workspace.

### Import Job

One upload event for one source file. It stores upload timestamp, parser status, extraction status, review status, and any import-level errors.

### Source File

The original uploaded document. Examples include:

- `final_boq.xlsx`
- `supplier_quote_abc.pdf`
- `invoice_1042.jpg`
- `purchase_summary.xlsx`

A source file is evidence. It should not usually be classified as material or service because one file can contain many materials, services, suppliers, prices, notes, terms, and dates.

### Extracted Candidate

An AI-parsed candidate record waiting for human review. Candidates are not active memory until approved.

### Memory Record

A reviewed, reusable fact extracted from a source file.

Memory record types:

- Material
- Service
- Supplier
- Service provider
- Price / quote / purchase line
- Note / miscellaneous evidence

One source file can produce many extracted candidates and many approved memory records.

Example from one invoice:

- Supplier: `ABC Construction Supply`
- Material: `PVC Pipe 2 inch`
- Purchase line: `PVC Pipe 2 inch, quantity 30, unit pcs, unit price 120`
- Service: `Delivery / Trucking`
- Note: `Delivery included`

### Taxonomy Node

A category or subcategory. The POC starts with a seeded taxonomy:

- Civil
- Electrical
- Plumbing
- Services
- Suppliers/Providers

AI may suggest new subcategories based on document clues and construction knowledge, but humans approve or remap them.

### Evidence Link

A reference from a candidate or memory record back to the source file. Evidence should include the strongest available locator, such as file name, sheet, row, page, text snippet, or OCR region.

### Value History

Stores prior values when later approved imports update an existing memory record. Active values follow latest approved import wins, but earlier values remain inspectable.

## Memory Record Fields

Each approved memory record should store:

- Raw extracted text.
- Normalized name.
- Record type.
- Category and subcategory.
- Dynamic attributes such as size, brand, spec, unit, quantity, price, date, payment terms, or delivery terms.
- Linked supplier or service provider when detected.
- Source evidence.
- AI confidence before review.
- Review decision and reviewer edits.
- Active or inactive state.

The POC should avoid forcing every construction detail into fixed columns. It should keep enough fixed structure for retrieval while preserving flexible attributes for messy real-world documents.

## AI Responsibilities

AI should propose:

- Candidate records from the parsed source file.
- Memory record type.
- Normalized name.
- Category and subcategory.
- Dynamic attributes.
- Supplier or provider links.
- Evidence references.
- Confidence level.
- Reasoning for classification when useful.

AI output is suggestive, not authoritative. Human review determines what becomes active memory.

Example:

```text
Raw item: THHN WIRE #12
Record type: Material
Suggested category: Electrical
Suggested subcategory: Wires and Cables
Confidence: High
Reason: Description contains wire type and gauge.
```

For unclear records:

```text
Raw item: Concrete coring, 4 holes
Record type: Service
Suggested category: Services
Suggested subcategory: Specialty Works
Confidence: Medium
Reason: Description appears to describe a site service, but the service category may need reviewer confirmation.
```

## Search And Retrieval

For the POC, search is within one completed project memory. It is not cross-project similarity search.

Supported query types:

- Search by material or service name, including fuzzy or different wording.
- Search by category or subcategory, such as electrical wires or plumbing pipes.
- Search by supplier or service provider.
- Search by price, quantity, unit, or spec when extracted.
- Search for all records from a source file.
- Ask simple natural-language questions such as:
  - Who supplied PVC pipes?
  - Show hauling services.
  - What electrical wires were used?
  - Which items had unit prices?
  - Where did this supplier appear in the project files?

Every result should show:

- Normalized name.
- Record type.
- Category and subcategory.
- Key extracted attributes.
- Source file reference.
- Confidence or review status.
- Simple explanation of why it matched.

## POC Architecture

The POC should be a small end-to-end app because human review is part of the proof.

Core components:

- Project Workspace: holds one completed project memory.
- Import UI: uploads one file at a time and shows import status.
- Parsing Service: extracts text, tables, and OCR content depending on file type.
- AI Extraction and Normalization Service: proposes candidates, record types, categories, subcategories, attributes, evidence, and confidence.
- Review Queue: lets the human approve, edit, reject, merge, recategorize, or request re-parse.
- Memory Store: stores approved memory records, source evidence, value history, taxonomy nodes, and active values.
- Search/Retrieval Layer: combines structured filters with semantic search over normalized names, raw text, attributes, and evidence snippets.
- Scorecard Module: stores golden questions, expected answers, actual results, scoring, and failure reasons.

Data flow:

```text
One completed project
  -> upload one source file
  -> parse file
  -> AI extracts candidates
  -> human reviews candidates
  -> approved records enter active memory
  -> memory becomes searchable
  -> golden questions test retrieval quality
  -> scorecard identifies what worked and what failed
```

The technical priority is traceability over automation. Every useful record should be explainable back to source evidence and a human approval decision.

## Error Handling And Edge Cases

### Import And File Errors

- Unsupported file type: mark import job as unsupported and allow user to add a note.
- OCR or parsing failure: show failed status and allow retry or manual extraction note.
- Empty extraction: mark as no candidates found, not success.
- Duplicate upload: warn that the file may already exist, but allow import if user confirms.
- Very large file: reject with a POC file-size limit and mark as out of POC scope.

### Extraction And Review Errors

- Low-confidence candidates go to review with a warning.
- Ambiguous item/service type stays as needs review.
- AI-suggested new subcategories require human approval.
- Conflicting values use latest approved import wins.
- Older conflicting values remain in value history.
- Rejected records remain in rejected history for POC analysis but do not appear in active search.

### Search And Retrieval Errors

- No results: show that no reviewed memory record was found.
- Ambiguous query: return likely matches with reasons instead of forcing one answer.
- Missing evidence: mark as weak record.
- Wrong golden-test result: score it and tag failure cause.

## Testing And Scorecard

The POC should be judged with a scorecard, not just a demo.

Test inputs:

- One completed project.
- A small realistic set of mixed files, uploaded one at a time.
- Seed taxonomy.
- Human-reviewed approved memory records.
- 20-30 golden retrieval questions created after review.

Scorecard dimensions:

- Parsing coverage: how many useful rows/items were extracted from each file?
- Extraction accuracy: how many candidate fields were correct before human edits?
- Normalization accuracy: how often AI proposed the right type, normalized name, category, and subcategory?
- Review efficiency: how many candidates were approved as-is, edited, rejected, or merged?
- Search relevance: how many golden questions returned the expected record and evidence?
- Evidence quality: how often results linked back to usable source file references?
- Data readiness: which fields and file types were useful, missing, noisy, or unreliable?
- Recommendation readiness: whether the resulting memory seems strong enough to support a future starter-pack feature.

Suggested early POC targets:

- At least 70% of useful candidates are extracted from structured Excel/PDF tables.
- At least 60% of candidates are approved or lightly edited rather than rejected.
- At least 70% of golden search questions return correct or partially correct results.
- Every approved memory record has at least one source evidence link.
- The scorecard identifies the top data gaps before MVP.

These numbers are early POC targets, not product-quality guarantees.

## Decision Summary

- Use Approach 2: Single-Project Memory Lab.
- Use one completed project only.
- Import one file per upload.
- Treat source files as evidence containers, not memory records.
- Allow one source file to produce many memory records.
- AI proposes memory record type, category, subcategory, attributes, and confidence.
- Human approval is required before active memory is updated.
- Use latest approved import wins for active values.
- Preserve previous values and evidence history.
- Test within-project memory retrieval, not cross-project similarity.
- Judge the POC with a scorecard across parsing, normalization, review, retrieval, evidence, data readiness, and recommendation readiness.
