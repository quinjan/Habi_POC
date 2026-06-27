# Create Review Ready Output Atomically

When processing produces reviewable candidates, the worker will persist the Review Batch, Extracted Candidates, candidate count, diagnostics, Review Batch ID, finished timestamp, and `review_ready` Processing Job status in one database transaction. A Processing Job should not become `review_ready` unless the reviewer-facing batch and candidates are fully created.
