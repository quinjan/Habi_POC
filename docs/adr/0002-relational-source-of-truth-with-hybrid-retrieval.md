# Relational Source Of Truth With Hybrid Retrieval

Habi will use a relational data store as the authoritative system of record for projects, source submissions, candidates, review decisions, taxonomy, imported memory records, evidence, archive state, and history, while using embeddings as a retrieval index over reviewer-approved active memory and evidence snippets. This preserves enforceable trust boundaries and project isolation while still letting AI search semantically across construction wording, source text, normalized names, and evidence-backed records.

Project isolation is enforced in the backend and database, not by frontend filtering. Project-owned records carry `project_id` directly or through required parents, relational constraints preserve ownership, and backend APIs scope queries, imports, evidence inspection, taxonomy decisions, and search to the selected project.

Pending candidates, rejected candidates, and archived memory records are excluded from normal AI search unless a specific source/history view intentionally exposes them. The LLM generates answers from retrieved project-scoped records and cited evidence blocks rather than reading the whole database or treating vector matches as truth.

Normal Search uses a two-stage retrieval pipeline: first retrieve active approved memory records and evidence snippets for the selected project using structured filters, full-text search, and vector similarity; then rerank and assemble a compact answer context before asking the LLM to respond. Source/history inspection and analytics questions are separate retrieval modes because prompts about rejected candidates, parsing failures, archived records, whole-file summaries, or structured totals require different scopes and rules.
