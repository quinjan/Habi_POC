# Use Small Backend Services For Review Lifecycle And Import Rules

Issue #4 will move Review Batch lifecycle rules and import rules out of route handlers into small backend services. The API remains workflow-shaped, while services own status recalculation, duplicate conflict validation, candidate decision changes, close-with-no-import validation, import gates, active Project Memory promotion, and merged-candidate evidence attachment.
