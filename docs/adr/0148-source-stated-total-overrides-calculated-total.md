# Source-Stated Total Overrides Calculated Total

When free-form source evidence states both quantity and unit price and also states a line total, the source-stated line total is authoritative even when it differs from deterministic multiplication. Habi preserves all grounded values, does not replace the total with `quantity × unit price`, and shows a non-blocking Candidate Detail warning with the calculated comparison and variance. The retained total remains Source Stated, not Calculated.

Habi creates an Evidence Annotation explaining the difference only when the source explicitly states a discount, tax, delivery charge, or another qualifying reason. An unexplained variance is not an annotation and does not invalidate the candidate; the reviewer sees the exact inputs, total, formula comparison, and warning before approval.
