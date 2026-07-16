# Contractor Assigned Resolves Internal Provider State

New Project Workspaces will require a Contractor Assigned text value, supplied to AI Extraction as project-scoped context. A named candidate defaults to Internal Provider State only when its provider name matches that value after case-and-whitespace normalization; aliases and fuzzy identity are out of scope and remain reviewer corrections. Migration initializes existing Project Workspaces with the sentinel `Internal`, which only permits explicit internal source wording to default Internal and never matches arbitrary named providers. Client or owner is not used for this resolution.

ADR 0117 clarifies the source-grounding invariant for XLSX: Contractor Assigned may classify an already extracted source Provider name, but it must never replace a different Provider name present in the source row.
