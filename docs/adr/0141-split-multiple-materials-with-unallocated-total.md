---
status: superseded by ADR-0142
---

# Split Multiple Materials With Unallocated Total

When one free-form source fact clearly purchases multiple distinct Materials, GPT-5.5 will create one Material Purchase Line candidate per Material rather than linking multiple Materials to one line or inventing a composite Material name. Source-backed quantities and units remain on their respective candidates. If the source provides only a combined total, each candidate displays a review-visible Unknown price state and no candidate copies or allocates the combined value as its structured price.

The exact combined-total wording becomes a grounded general-qualifier annotation on every affected candidate under ADR 0123, and shared Provider or other supporting spans may ground each line independently. For example, `20 bags of cement and 10 lengths of rebar from Wilcon for a combined PHP 50,000` creates separate Cement and Rebar Purchase Lines with Unknown prices and the same combined-total qualifier. This preserves reusable Material identity and source completeness without fabricating per-item commercial facts.
