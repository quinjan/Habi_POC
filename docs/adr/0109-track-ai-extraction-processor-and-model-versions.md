# Track AI Extraction Processor And Model Versions

AI Extraction jobs will use `processor_name` to identify the stable extraction harness and prompt version, such as `ai_manual_free_form_v1`, while Processing Job diagnostics store the concrete model name used for the run. Separating processor version from model version lets Habi compare future extraction changes without confusing prompt/schema revisions with model selection.
