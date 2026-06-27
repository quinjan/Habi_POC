# Store Compact AI Extraction Diagnostics

AI Extraction should persist compact diagnostics such as model name, candidate counts, dropped-candidate count, and a short failure or warning summary, but should not store raw model responses in issue #18. The preserved Source Submission remains the source of evidence, while diagnostics support debugging and scorecard work without duplicating source text or exposing malformed model output as product data.
