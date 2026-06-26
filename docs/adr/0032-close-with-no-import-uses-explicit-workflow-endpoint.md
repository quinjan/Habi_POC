# Close With No Import Uses Explicit Workflow Endpoint

Review Batches will use an explicit workflow endpoint for closing with no import. The backend action will reject already imported batches, unresolved candidates, and any final candidate outcome still included for import before setting `review_closed_no_import`, preserving candidates and duplicate groups as batch history.
