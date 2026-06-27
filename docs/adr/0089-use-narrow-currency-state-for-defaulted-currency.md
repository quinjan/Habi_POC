# Use Narrow Currency State For Defaulted Currency

The first AI Extraction slice will represent currency provenance with a narrow candidate field such as `currency_state`, rather than introducing a general per-field provenance model. Currency needs this explicit state because Habi defaults missing currency to PHP for the POC, so reviewers must be able to distinguish source-stated currency from defaulted or unknown currency.
