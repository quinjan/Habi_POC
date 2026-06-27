# Taxonomy Defaults Are Returned With Review Candidates

Project-local taxonomy defaults should be exposed through candidate and Review Batch APIs rather than a standalone taxonomy-default resolution endpoint in this slice. Review responses can include the raw AI-suggested category path, any defaulted Resolved Category Path from approved or mapped Taxonomy Decisions, and provenance text for the reviewer UI.
