# AI Extraction Defaults Missing Currency To PHP

When AI Extraction finds a price but the source text does not state a currency, Habi will default the candidate currency to PHP, matching the POC assumption for Philippine project records. This default does not make Habi single-currency: if the source text explicitly uses another ISO 4217 currency, AI Extraction should preserve that currency in the candidate for reviewer confirmation. Candidates whose currency was defaulted should carry review-visible provenance that the value came from a default rather than directly from the source text.
