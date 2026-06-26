# Processing Job Statuses Distinguish Review Readiness

Processing Jobs will use a narrow lifecycle of `queued`, `processing`, `review_ready`, `no_candidates_found`, and `failed` rather than a vague completed status. This makes the product outcome visible: processing either produced reviewable Extracted Candidates, completed without useful candidates, or failed before review readiness.
