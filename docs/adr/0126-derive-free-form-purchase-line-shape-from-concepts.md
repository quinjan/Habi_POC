---
status: superseded by ADR-0142
---

# Derive Free-Form Purchase Line Shape From Concepts

The GPT-5.5 free-form contract will return only the candidate's grounded linked-concept collection and will not return a separate Purchase Line `line_type`. Habi derives Material from exactly one Material, Service from exactly one Service, and Bundled from exactly one Material plus exactly one Service; an empty collection, duplicate concept type, more than two concepts, or any other combination fails validation and receives the configured `xhigh` repair. This extends ADR 0114's Bundled Purchase Line invariant and supersedes ADR 0086's two-type model contract for free-form extraction, preventing a model-supplied shape label from contradicting the concepts that reviewers and import actually use.
