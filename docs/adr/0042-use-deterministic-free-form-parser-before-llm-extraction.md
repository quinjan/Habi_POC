# Use Deterministic Free-Form Parser Before LLM Extraction

The first free-form Manual Source Entry slice will use a deterministic parser stub rather than an LLM call. This lets Habi prove the Source Submission, Processing Job, Review Batch, candidate creation, and no-candidates-found workflow with stable behavior-level tests before adding variable AI extraction behind the same Processing Job boundary.
