# One-File XLSX Source Upload Processing Design

## Context

GitHub issue #6 adds one-file `.xlsx` Source File ingestion to the selected Project Workspace. It extends, but does not replace, Manual Source Entry. Each confirmed upload is an immutable Source Submission with exactly one Source File and one Processing Job. The source remains outside Project Memory until AI-proposed Purchase Line candidates pass server validation, human review, and the existing import gates.

Issue #6 supersedes the older PRD statement about duplicate-upload warnings. XLSX uploads perform no duplicate-content lookup, warning, blocking, or confirmation. The SHA-256 checksum exists only for integrity and audit.

Relevant decisions include ADR-0004 (filesystem originals and derived artifacts), ADR-0107 (atomic review-ready output), ADR-0109 (processor and model version diagnostics), ADR-0111 (visible AI candidates require complete two-level taxonomy), and ADR-0113 (persisted worksheet profiles before stateless chunk extraction).

## Goals

- Accept exactly one explicitly confirmed `.xlsx` upload for a selected Project Workspace.
- Reject unsupported or over-size requests before creating permanent files or database records.
- Preserve every accepted original byte-for-byte with audit metadata.
- Create inspectable derived table artifacts for readable, in-limit visible worksheets.
- Use a stateless AI profile pass followed by independent bounded extraction chunks.
- Admit only fully classified Purchase Line candidates with server-verified same-region row evidence.
- Preserve the existing Review Batch and import trust boundaries.
- Show upload guidance, job outcomes, recovery information, and spreadsheet evidence in the client.

## Non-goals

- Multiple-file or bulk upload.
- `.xls`, `.xlsm`, CSV, PDF, image, or other source formats.
- Duplicate-upload detection.
- Cancellation, automatic AI retry, or direct reprocessing.
- A source-file download screen or raw artifact/profile viewer.
- Formula, macro, external-link, image, chart, comment, or attachment execution or extraction.
- Cross-sheet joins or persistent model conversation state.

## Chosen Approach

Create a dedicated XLSX workflow module behind the existing upload, Processing Job, Review Batch, and import interfaces. Workbook parsing, storage layout, artifact creation, AI orchestration, and locator validation remain local to that module. Callers interact through one upload endpoint and the existing worker/job/review flow.

This is preferred over extending the manual processor in place because XLSX processing has distinct upload, storage, profiling, chunking, evidence, and failure semantics. It is preferred over flattening worksheets into text because flattening loses table-region structure and coordinate-verifiable evidence.

## Configuration

Add a single `XlsxProcessingConfig` loaded from environment variables:

| Setting | Environment variable | Default |
|---|---|---:|
| Shared storage root | `HABI_STORAGE_ROOT` | `/app/data` in containers; `.habi-data` for local execution |
| Maximum upload bytes | `HABI_XLSX_MAX_UPLOAD_BYTES` | `26214400` |
| Maximum visible worksheets | `HABI_XLSX_MAX_VISIBLE_WORKSHEETS` | `10` |
| Maximum visible non-empty rows | `HABI_XLSX_MAX_NON_EMPTY_ROWS` | `2000` |
| Maximum visible non-empty cells | `HABI_XLSX_MAX_NON_EMPTY_CELLS` | `50000` |
| Maximum non-empty rows per extraction chunk | `HABI_XLSX_EXTRACTION_CHUNK_ROWS` | `100` |

The configured OpenAI model continues to come from `OPENAI_MODEL`, with the repository's current `gpt-5.4-nano` default. Limits and model selection are deployment configuration, not reviewer settings.

Compose mounts one named storage volume at the same path in the backend and worker containers. The storage root is ignored by git for direct local execution.

## Upload Interface

Add:

`POST /api/project-workspaces/{project_workspace_id}/source-files`

The request uses `multipart/form-data` with a `files` field represented as a list so the backend can enforce a count of exactly one instead of silently accepting one member of a repeated field. The successful `201` response contains the created Source Submission, Source File metadata, and queued Processing Job.

Validation occurs in this order:

1. Confirm the Project Workspace exists.
2. Require exactly one uploaded part.
3. Require a case-insensitive `.xlsx` filename suffix.
4. Stream the upload into a request-scoped temporary file while hashing and counting bytes.
5. Stop after `max_upload_bytes + 1`; return `413` and remove the temporary file.
6. Create the Source Submission, Source File, and Processing Job in one database transaction.
7. Move the temporary file atomically into its generated permanent path before committing.

Unsupported extension or invalid file count returns `422`. No MIME-type allowlist is used because declared MIME values are client-controlled and must be retained rather than trusted. A correctly named but corrupt or encrypted file is accepted at the upload boundary and fails during worker processing.

The permanent path never incorporates the user filename. It uses generated identifiers:

`source-files/{source_file_id}/original.xlsx`

If permanent storage or the database transaction fails, cleanup removes the newly moved file so the system does not leave a permanent file without its records.

## Persistence

### Source File

Add a `source_files` table containing:

- `id`
- `project_workspace_id`
- `source_submission_id`, unique and non-null
- `original_filename`
- `byte_size`
- `declared_mime_type`, nullable
- `uploaded_at`
- `sha256_checksum`
- `storage_path`, unique and stored relative to `HABI_STORAGE_ROOT`

The upload creates `SourceSubmission.submission_type = "source_file"` and a Processing Job with `source_type = "source_file"` and `processor_name = "ai_xlsx_purchase_lines_v1"`.

### Worksheet Artifact

Add a `worksheet_artifacts` table containing:

- `id`
- `project_workspace_id`
- `source_file_id`
- `worksheet_index`
- `worksheet_name`
- `artifact_path`, unique and relative to the storage root
- `non_empty_row_count`
- `non_empty_cell_count`
- `profile`, nullable JSON populated after a successful profile response
- `created_at`

The pair `(source_file_id, worksheet_index)` is unique. No write endpoint exists for artifacts or profiles.

Artifact files use:

`derived/{source_file_id}/worksheets/{worksheet_index}.json`

### Evidence Records

Generalize `EvidenceRecord` so one record refers to exactly one source kind:

- Make `manual_source_entry_id` nullable.
- Add nullable `source_file_id`.
- Add a database check constraint requiring exactly one of those columns.

Manual evidence behavior remains unchanged. XLSX import evidence uses `source_label = original_filename` and stores the verified worksheet/region/row locator payload in `content`.

## Workbook Validation and Artifact Creation

Use `openpyxl` and open the preserved workbook twice without saving it:

- Formula view: `data_only=False`, retaining literal formula text.
- Value view: `data_only=True`, reading last-saved cached formula values.

The worker first attempts both opens. ZIP/package errors, encryption/password protection, false naming, or workbook load errors produce `failed`, with no artifacts, candidates, or Review Batch.

The workbook scan considers only visible worksheets and excludes hidden rows and columns. It counts hidden sheets, rows, and columns for compact diagnostics. A row is non-empty when at least one visible cell has literal content, a formula, or a cached value. A cell with formula text but no cached result counts toward workbook limits but is excluded from AI input.

The worker performs an early-abort limit scan before artifact generation. If visible worksheet count, non-empty row count, or non-empty cell count exceeds its configured limit, the original remains preserved and the Processing Job becomes `failed`. No artifacts are required for a workbook rejected at this post-open boundary.

For an in-limit workbook, create one artifact for every readable visible worksheet before any AI request. Hidden worksheets produce no artifacts. Each artifact contains:

```json
{
  "worksheet": {
    "name": "Purchases",
    "index": 0,
    "merged_ranges": ["A1:H1"]
  },
  "cells": [
    {
      "coordinate": "B31",
      "row": 31,
      "column": 2,
      "raw_value": "PVC pipe",
      "normalized_value": "PVC pipe",
      "displayed_text": "PVC pipe",
      "cell_type": "string",
      "number_format": "General",
      "formula": null,
      "is_bold": false,
      "has_fill": false
    }
  ]
}
```

`raw_value` is the literal value or cached formula result serialized to JSON-compatible data. `formula` separately retains formula text. `normalized_value` converts dates, datetimes, decimals, booleans, and strings into stable JSON representations. `displayed_text` provides deterministic best-effort text using the cached/literal value and number format; exact Excel rendering is not required. Merged ranges are recorded at worksheet level. Formula cells without cached results remain in the artifact with `raw_value = null` and do not enter profile or extraction input.

Write each artifact to a temporary path and atomically rename it. If artifact creation fails, mark the job `failed`, retain the original and already completed artifacts, and create no Review Batch.

## AI Provider Interface

Keep the true external seam at the AI provider. Extend it with two XLSX methods while preserving the existing manual extraction method:

```python
profile_worksheet(*, worksheet: dict, source_submission_id: int) -> dict

extract_worksheet_chunk(
    *,
    profile: dict,
    region: dict,
    rows: list[dict],
    context_rows: list[dict],
    source_submission_id: int,
) -> dict
```

Automated tests use a fake adapter. Production uses the existing OpenAI Responses API adapter.

Both production calls:

- use the configured model;
- use strict `text.format` JSON Schema output;
- set `store = false`;
- omit `previous_response_id` and conversation identifiers;
- send only the persisted profile, current bounded rows, and nearby read-only context needed for that call;
- state that workbook text is untrusted data and cannot alter instructions;
- persist no raw model response.

The current Responses API documents `text.format` with `type = "json_schema"`, `schema`, and optional `strict`, and documents `store` as the switch for later response retrieval: <https://developers.openai.com/api/reference/resources/responses/methods/create>.

## Worksheet Profile Schema

The profile response contains:

- `worksheet_name`
- `title_rows`: row numbers used only as context
- `header_rows`: row numbers used only as context
- `regions`, each with:
  - stable request-local `region_id`
  - `usable`
  - nullable `unusable_reason`
  - `header_row_numbers`
  - `body_start_row`
  - `body_end_row`
  - mapped columns for candidate fields

Server validation requires worksheet-name equality, existing row numbers, ordered body ranges, and columns that exist in the artifact. An unusable region must include a compact reason. Invalid profile structure is a technical failure. A valid profile with no usable regions is a normal no-candidate condition.

Persist each validated profile on its Worksheet Artifact before extraction begins.

## Chunking and Candidate Schema

For each usable region, select its non-empty visible body rows and split them into independent chunks of at most the configured 100 rows. Nearby title/header rows and immediately adjacent rows may be included in `context_rows`, but context rows do not count toward the chunk limit and cannot be the sole evidence for a candidate.

The XLSX extraction schema reuses the Purchase Line fields and complete two-level taxonomy requirement from manual AI extraction. Its evidence shape is:

```json
{
  "source_submission_id": 123,
  "source_file_id": 45,
  "worksheet": "Purchases",
  "region_id": "region-1",
  "primary_body_row": 31,
  "locators": [
    {"row": 31, "role": "body"},
    {"row": 30, "role": "context"}
  ]
}
```

Every visible candidate must have a valid `material` or `service` line type, non-empty name, confidence in `[0, 1]`, complete top-level category and subcategory, matching source IDs, matching worksheet and region, one or more distinct artifact-backed row locators, and at least one body locator. `primary_body_row` must name one of its body locators.

Invalid candidate proposals are dropped and counted in diagnostics. No proposal is persisted until every required profile and extraction call for the workbook has completed successfully. This guarantees that a technical failure cannot leave partial candidates.

## Processing Job Flow

The worker recognizes `ai_xlsx_purchase_lines_v1` only when an AI provider is available, matching current free-form AI job behavior.

Processing steps are:

1. Claim one queued job with the existing row-locking behavior.
2. Mark it `processing` and set `started_at`.
3. Load and validate the Source File record and preserved path.
4. Open and scan the workbook; enforce post-open limits.
5. Persist derived artifacts for all readable visible worksheets.
6. Profile each artifact and persist validated profiles.
7. Execute independent region chunks and collect candidate proposals in memory.
8. Validate taxonomy and evidence locators against artifacts and profiles.
9. Derive the terminal outcome.
10. When candidates exist, atomically create the Review Batch and candidates and update the job to `review_ready` with diagnostics, count, batch ID, and `finished_at`.
11. Otherwise update the job to `failed` or `no_candidates_found` without a Review Batch.

The processor catches expected workbook, limit, artifact, provider, and schema errors and returns a terminal outcome so the session can commit the job state and any completed non-AI artifacts. Unexpected errors are converted by the worker into a failed job with a compact error message rather than leaving it indefinitely processing.

## Terminal Outcomes

| Condition | Job outcome | Original | Artifacts | Review Batch |
|---|---|---|---|---|
| Invalid count/type or over upload-size | Request rejected | No | No | No |
| Corrupt/encrypted/false `.xlsx` | `failed` | Yes | No | No |
| Post-open limit exceeded | `failed` | Yes | No | No |
| Artifact failure | `failed` | Yes | Completed artifacts retained | No |
| Technical profile/extraction failure | `failed` | Yes | Yes | No |
| No usable region or no valid candidate | `no_candidates_found` | Yes | Yes | No |
| Some unusable regions and at least one valid candidate | `review_ready` | Yes | Yes | Yes |
| All required calls succeed with valid candidates | `review_ready` | Yes | Yes | Yes |

Technical failures include provider exceptions, malformed structured output, and invalid profile schemas. Invalid individual candidate proposals are normal drops. If all proposals are dropped, the XLSX job ends `no_candidates_found`, consistent with issue #6.

## Diagnostics

Diagnostics remain compact and include:

- processor, provider, and concrete model;
- original filename;
- visible/hidden worksheet counts;
- hidden row and column counts;
- visible non-empty row and cell counts;
- artifact count;
- usable and unusable region counts;
- profile and extraction request counts;
- configured chunk-row limit and actual chunk count;
- raw, valid, and dropped candidate counts;
- concise skip, limit, warning, or failure summary;
- no raw workbook text and no raw model response.

`error_message` contains the concise technical exception text needed by the local POC disclosure.

## Review and Import Evidence

Review Batch responses continue to return candidate payloads. The client formats XLSX evidence from the verified payload as:

`purchase-log.xlsx - Purchases - rows 31-32`

The primary body row is visually emphasized and supporting rows remain visible. Manual Source Entry evidence continues to display its existing Source Submission reference.

Review lifecycle readiness recognizes a Source File with valid candidate evidence as satisfying the source-evidence gate. During import, one Evidence Record is created for each approved candidate's verified locator set and linked to the Purchase Line and associated Material/Service/Provider Memory Records using existing behavior. Merged candidate evidence promotion supports both source kinds.

## Client Design

Keep the existing Manual Source Entry form. Add a distinct Excel upload panel above it in Upload / Review with:

- the exact guidance copy from issue #6;
- a single-file input with `.xlsx` accept filtering;
- selected filename and size;
- client-side extension and 25 MiB checks;
- an explicit **Upload and process** submit button;
- disabled/submitting state and validation feedback.

The generic API request helper must not force `Content-Type: application/json` for `FormData`; the browser supplies the multipart boundary.

Processing Job list items add original filename when the source is a file, submission timestamp, status, candidate count when available, and a concise outcome/diagnostic summary. `failed` and `no_candidates_found` states show generic recovery guidance. Failed jobs expose `error_message` inside a collapsed **Technical details** disclosure. Manual jobs retain their current labels and behavior.

Candidate Detail shows filename, worksheet, all verified rows, and primary body-row emphasis.

## Testing Strategy

Follow vertical red-green cycles rather than writing the suite horizontally.

### Backend behavior seams

1. POST multipart upload rejects zero/multiple files, non-XLSX names, and over-25-MiB content without creating records or permanent files.
2. A valid upload returns Source Submission, Source File metadata, and a queued job; stored bytes and SHA-256 match the submitted bytes.
3. Uploading identical bytes twice creates distinct submissions, files, paths, and jobs.
4. A corrupt or falsely named file is preserved and becomes failed when the worker runs.
5. A readable over-limit workbook becomes failed with the expected limit diagnostic and no Review Batch.
6. A realistic workbook fixture produces artifacts only for visible worksheets and excludes hidden rows/columns while recording counts.
7. Artifact content covers formulas with and without cached values, merged ranges, types, formats, coordinates, bold, and fill signals.
8. A fake AI adapter observes one profile call per artifact and independent chunks of at most 100 non-empty body rows.
9. Empty/unusable profiles produce `no_candidates_found`; partial unusable regions can still produce `review_ready`.
10. A technical profile or extraction failure retains artifacts and produces no partial candidates or Review Batch.
11. Invalid taxonomy or locators are dropped; same-region verified locators produce review-ready candidates.
12. Review APIs return filename/sheet/row evidence and import promotes it into source evidence.

Backend behavior tests use the dedicated Postgres test database and temporary filesystem storage. XLSX fixtures are generated with `openpyxl` and saved as real workbook bytes. Tests use the HTTP interface and worker entry point; direct ORM/file assertions are limited to artifact and immutable-storage behaviors that intentionally have no viewer endpoint.

### AI adapter tests

Use a fake OpenAI client to verify separate strict profile and extraction schemas, the configured model, `store = false`, absence of prior-response state, and successful/invalid structured-response parsing. Automated tests never call the live OpenAI API.

### Frontend behavior seams

1. The upload guidance is always visible in the upload panel.
2. File selection enforces one `.xlsx` and the size limit before submission.
3. **Upload and process** sends multipart form data and refreshes the queue.
4. Queue items show filename, time, status, counts, summaries, recovery guidance, and collapsed technical details.
5. Candidate Detail displays and emphasizes spreadsheet row evidence.

### Final verification

- Regenerate `backend/openapi.json` and `frontend/src/api/generated.ts`.
- Run all backend tests against the dedicated Postgres database.
- Run all frontend tests.
- Run the frontend production build.
- Confirm no live OpenAI request occurred during automated verification.

## Dependency and Deployment Changes

- Add `openpyxl` and `python-multipart` to backend requirements.
- Add the new Alembic migration after revision `20260627_0006`.
- Add shared storage volume/configuration to Compose and document local storage configuration.
- Correct the environment template's OpenAI base URL entry while adding the XLSX configuration values.

## Compatibility

Manual Source Entry endpoints, processor names, review behavior, and existing payloads remain supported. Processing Job summaries gain nullable Source File metadata rather than changing manual submission semantics. Existing Evidence Records are migrated without losing their Manual Source Entry relationship. No existing imported memory behavior is intentionally changed beyond allowing verified Source File evidence to satisfy the same gates.
