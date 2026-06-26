# Candidate Decisions Remain Editable Until Terminal Batch Status

Candidate decisions, reviewed payloads, merge metadata, and duplicate-group membership remain editable while a Review Batch is non-terminal. Each change triggers backend lifecycle recalculation and duplicate conflict checks; edits are blocked once the batch is imported or explicitly closed with no import.
