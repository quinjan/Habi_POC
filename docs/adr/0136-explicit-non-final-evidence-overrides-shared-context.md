# Explicit Non-Final Evidence Overrides Shared Context

For GPT-5.5 free-form extraction, candidate-local source wording that establishes an estimate, budget, canvass option, alternative quote, proposal, pending approval, non-selection, non-award, cancellation, or another non-final status overrides a broader supporting heading that otherwise suggests final/as-used purchasing. The affected span produces no Purchase Line unless other local source evidence clearly establishes that the fact later became final/as-used. Project Memory cannot override this source precedence.

This is a semantic GPT-5.5 prompt rule with positive and negative scorecard examples, not a backend keyword blacklist: construction wording and negation must be interpreted in context. The source remains preserved, but an excluded non-final option does not become a workflow-noise annotation or qualification on another candidate.
