# LLM Outputs Validated Candidate Proposals

The Habi POC will treat LLM extraction output as structured candidate proposals that the app validates and stores, not as direct writes into project memory. The LLM may propose record type, normalized name, fields, taxonomy path, confidence, evidence locators, duplicate matches, merge suggestions, and short reasoning, but the backend validates the JSON candidate schema before any reviewer sees it.

Only reviewed import code can create or update active memory records. Merge suggestions from the LLM require human approval, and a merged candidate counts as resolved only when the final merged record satisfies the same import rules as any other record: source evidence, resolved category path, required purchase-line links, and project-scoped review completion.
