# Profile XLSX Worksheets Before Chunked AI Extraction

XLSX processing will first use AI to produce a persisted, structured profile of each visible worksheet, identifying its title/header context and usable table regions. Candidate extraction will then run as independent, bounded chunk requests supplied with that profile rather than through a persistent AI conversation; this keeps retries and evidence grounding deterministic, avoids conversation-state lifecycle and retention complexity, and supports different model context-window limits through configuration.

ADR 0117 refines the post-profile step: exact visible headers may deterministically enrich the profile, and sufficiently explicit body rows are converted into source-grounded candidates before AI fallback is accepted for incomplete or ambiguous rows.
