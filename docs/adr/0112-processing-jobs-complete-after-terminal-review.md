# Processing Jobs Complete After Terminal Review

Processing Jobs may move from `review_ready` to `completed` once their Review Batch reaches a terminal outcome, either imported or review closed with no import. This revises the earlier ADR-0040 stance against a generic completed status: before review readiness, statuses still describe source-processing outcomes, but after reviewer disposition the job/review queue needs a terminal label so resolved Review Batches do not remain actionable in the Upload / Review queue.

