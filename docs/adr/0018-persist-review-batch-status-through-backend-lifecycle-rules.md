# Persist Review Batch Status Through Backend Lifecycle Rules

Review Batch status will be persisted for simple workflow display, but the backend will update it only through lifecycle rules that recalculate status from candidate actions and import gates. This keeps the UI and API easy to read while preserving the trust boundary: `ready_to_import` means the backend believes import would succeed right now, and the import endpoint still re-checks the same gates before creating active Project Memory.

When all candidate outcomes are excluded but the reviewer has not explicitly closed the batch, the persisted status remains `review_in_progress`; the API may expose that close-with-no-import is available as derived action state.

`ready_to_import` requires at least one approved Surviving Candidate whose final reviewed payload satisfies import gates; batches with only excluded outcomes can be explicitly closed with no import, but are not ready to import.
