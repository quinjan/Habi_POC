# Profile XLSX Worksheets Before Chunked AI Extraction

XLSX processing will first use AI to produce a persisted, structured profile of each visible worksheet, identifying its title/header context and usable table regions. Candidate extraction will then run as independent, bounded chunk requests supplied with that profile rather than through a persistent AI conversation; this keeps retries and evidence grounding deterministic, avoids conversation-state lifecycle and retention complexity, and supports different model context-window limits through configuration.
