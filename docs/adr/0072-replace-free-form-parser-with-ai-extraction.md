# Replace Free-Form Parser With AI Extraction

Free-form Manual Source Entry processing will replace the temporary deterministic parser with AI Extraction in the background worker slice. If AI Extraction cannot produce valid extracted candidate proposals, Habi should mark the Processing Job as `failed` rather than falling back to deterministic parsing, because the parser existed only to prove the Source Submission, Processing Job, and Review Batch workflow before the real AI Extraction path was available.
