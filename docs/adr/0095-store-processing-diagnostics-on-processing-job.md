# Store Processing Diagnostics On Processing Job

Compact AI Extraction diagnostics will live on the Processing Job as a JSON diagnostics field in the POC. This keeps model name, candidate counts, dropped-candidate count, and short warning or failure summaries close to the durable processing outcome without introducing a separate diagnostics table before Habi needs query-heavy or user-facing processing history.
