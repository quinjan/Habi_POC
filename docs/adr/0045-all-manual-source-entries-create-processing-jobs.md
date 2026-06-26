# All Manual Source Entries Create Processing Jobs

Both structured-row and free-form-text Manual Source Entries will create Processing Jobs. Structured rows may complete synchronously into `review_ready`, while free-form text can run through parsing before reaching `review_ready`, `no_candidates_found`, or `failed`, giving every Source Submission durable processing history through one workflow.
