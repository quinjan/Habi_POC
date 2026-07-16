# Group Coherent Same-Type Annotation Clauses

GPT-5.5 free-form extraction will return one Evidence Annotation when adjacent wording forms one coherent term with the same Evidence Annotation Type and target, even when that term contains multiple schedule parts or actions. `50% down payment and 50% after testing and commissioning` is one Purchase-Line payment-terms annotation, and `Delivery and unloading included` is one Purchase-Line delivery-terms annotation. The model splits proposals when type or target changes, or when source wording establishes genuinely independent terms.

This granularity combines with ADR 0123's cross-candidate and explicit multi-target replication without deduplicating distinct targets. It fixes the supplied four-Purchase-Line regression fixture at 15 expected annotations: splitting the two halves of its payment schedule would be an incorrect sixteenth annotation.
