# Calculate Free-Form Line Totals From Grounded Inputs

When GPT-5.5 free-form output grounds a numeric quantity, compatible unit, currency, and unit price but the source does not state a line total, Habi may deterministically calculate `quantity × unit price` as the Purchase Line total. The model contract returns grounded `quantity`, `unit_price`, and optional `source_stated_line_total` values with exact excerpts; GPT-5.5 never authors the arithmetic result. When `source_stated_line_total` is null and validation confirms compatible numeric inputs, Candidate Detail labels the backend total Calculated, shows the formula and grounded inputs, and keeps it distinct from a source-stated price or Defaulted Field State.

The calculation counts as an individually attributable price under ADR 0146, so independently calculable concepts become separate Purchase Lines. Habi does not calculate when discounts, taxes, tiering, mixed units, ranges, package pricing, or other wording makes the arithmetic ambiguous; those cases retain a source-stated combined bundle price or an Unknown price as applicable. The backend uses decimal arithmetic and never asks the model to resolve the calculation.

When the source also states a total, ADR 0148 makes that source value authoritative and uses arithmetic only for a non-blocking comparison warning.
