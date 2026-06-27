# AI Extraction Drops Ambiguous Purchase Line Types

AI Extraction will create Purchase Line candidates only when the model can classify the line as `material` or `service`. Ambiguous extracted facts should be omitted from the candidate output rather than creating candidates that cannot satisfy import gates; if all possible facts are ambiguous or unusable, the Processing Job should complete as `no_candidates_found`.
