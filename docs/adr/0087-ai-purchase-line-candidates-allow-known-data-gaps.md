# AI Purchase Line Candidates Allow Known Data Gaps

AI Extraction may create Purchase Line candidates when it has a useful item or service name and a `material` or `service` line type, even if quantity, unit, price, provider, or date are missing. Missing fields should flow into the existing unknown field states during review and import rather than causing the AI to invent values or discard otherwise useful source-backed purchase facts.
