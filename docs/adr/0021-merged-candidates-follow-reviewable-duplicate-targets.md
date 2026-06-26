# Merged Candidates Follow Reviewable Duplicate Targets

The POC will model duplicate resolution as an explicit merge relationship that can be changed or undone during review. A Merged Candidate points to another candidate in the same Review Batch and does not create its own import record; if the target is approved, the duplicate is included through that target, and if the target is rejected, the duplicate is excluded with that duplicate group. Unmerging restores the candidate to needing its own approved or rejected review outcome.
