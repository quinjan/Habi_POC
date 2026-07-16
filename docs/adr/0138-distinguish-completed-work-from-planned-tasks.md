# Distinguish Completed Work From Planned Tasks

GPT-5.5 free-form extraction will treat source-grounded completed or performed construction work as a Service Purchase Line under ADR 0137 even when price, Provider, or other commercial fields are absent. Imperative instructions, future tasks, work pending approval, planned work, and other not-yet-completed activity are non-final under ADR 0136 and produce no Purchase Line. For example, `Installed 10 doors using our crew` is eligible completed work, while `Install 10 doors tomorrow` and `Ceiling installation pending approval` are excluded.

The prompt and real-model scorecard must test tense, aspect, and intent in context rather than relying on deterministic verb or suffix matching. Excluded planned work does not become an Evidence Annotation or workflow-noise candidate.
