# Do Not Silently Omit Free-Form Annotations

GPT-5.5 free-form extraction will not apply the implementation's existing 20-annotation cap. Habi retains every distinct, valid, source-grounded Evidence Annotation proposal returned for a candidate and deduplicates only proposals with the same normalized text, type, target, and exact source range on that same candidate. A qualifier replicated across different candidates under ADR 0123 remains distinct. Structured Manual Source Entry and XLSX annotation limits are unchanged.

An invalid shape, unavailable target, ungrounded excerpt, workflow-noise proposal, or other dropped annotation makes its free-form candidate invalid rather than being silently removed. The candidate or whole result follows the centralized GPT-5.5 repair policy, and an unrepaired annotation failure fails the complete Processing Job under ADR 0124. This makes annotation completeness and zero workflow noise enforceable extraction outcomes rather than warning-only diagnostics.

Source wording intentionally excluded because no annotation target can be determined under ADR 0134 is not a dropped valid annotation and does not trigger repair or failure.
