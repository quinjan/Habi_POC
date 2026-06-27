# Manual Source Submit Returns Queued Job

After background processing is introduced, Manual Source Entry creation will return the preserved Source Submission, the Manual Source Entry detail, and a queued Processing Job, but not an immediate Review Batch or Extracted Candidates. The frontend should poll the Processing Job status and load the Review Batch only when the job reaches `review_ready`, keeping source submission separate from asynchronous review preparation.
