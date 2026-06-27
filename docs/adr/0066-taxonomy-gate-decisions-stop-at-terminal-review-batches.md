# Taxonomy Gate Decisions Stop At Terminal Review Batches

Taxonomy Gate decisions cannot be changed after a Review Batch reaches a terminal status such as imported or review closed with no import. Approved Taxonomy Decisions may create project taxonomy nodes immediately, and those nodes remain even if the originating Review Batch is later closed with no import because taxonomy approval is separate from candidate import. Taxonomy cleanup after terminal review should happen through Project Workspace taxonomy node edit or rename workflows, not by changing historical candidate gate decisions.
