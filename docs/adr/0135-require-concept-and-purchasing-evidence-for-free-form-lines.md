# Require Concept And Purchasing Evidence For Free-Form Lines

GPT-5.5 free-form extraction will create a Purchase Line candidate only when verified primary or supporting spans establish both at least one exact observed Material or Service and a final/as-used project purchasing assertion for that concept. A Provider name, price, quantity, annotation-like qualifier, or other commercial fragment without a grounded concept and purchasing status cannot create a candidate. Terse body text may rely on an exact supporting heading such as `Final purchases` or `Approved installed works`, but Project Memory never supplies either missing source requirement.

Known gaps in unit, price, date, or Provider remain permitted under ADR 0087 once the minimum threshold is satisfied. Evidence Annotations remain subordinate qualifications and never create Purchase Lines under ADR 0134. The free-form prompt and real-model scorecard must include positive and negative examples that separate final/as-used purchasing facts from unsupported fragments, plans, estimates, and workflow text.

ADR 0137 clarifies that a coherent transaction or completed-work shorthand satisfies purchasing context by default when no non-final evidence is present; an explicit purchase verb is not required.
