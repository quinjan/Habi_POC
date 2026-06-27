# Taxonomy Renames Update Live Displayed Category Paths

When a reviewer renames or edits a Taxonomy Node inside a Project Workspace, existing imported Memory Records that reference that node should display the updated Resolved Category Path. Habi treats taxonomy edits as corrections to the project's live taxonomy language, not as creation of a new category, while full import-time taxonomy history remains deferred unless a later audit/history slice explicitly adds it. Issue #7 rename/edit is name-only: it must not support reparenting subcategories to different Top-Level Categories.
