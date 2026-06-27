# Review Batch Uses Taxonomy Defaults And Batch Draft Save

The multi-candidate Review Batch flow treats complete AI-suggested two-level taxonomy as the default reviewed category for visible Extracted Candidates, instead of requiring a separate review-time Approve Taxonomy action. Reviewer changes to that default are saved immediately as mapped Taxonomy Decisions that update affected candidate reviewed category fields, while include/exclude choices remain local batch draft state until Save or Import persists them in one workflow call.
