# Structured Rows Use Deterministic Worker Processing

Structured-row Manual Source Entries will go through the same background Processing Job pipeline as free-form entries, but they will not call AI Extraction in issue #18. The worker should reuse the existing deterministic structured-row candidate creation logic, while later AI-suggested category path behavior for structured rows can be added as a separate processing step if needed.
