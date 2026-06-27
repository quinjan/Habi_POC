# Worker Refuses To Start Without AI Provider Config

The background worker will validate required AI provider configuration before claiming Processing Jobs. Missing configuration such as `OPENAI_API_KEY` or the configured extraction model is an operator setup problem, so the worker should refuse to start rather than marking queued Source Submissions as failed and forcing reviewers to resubmit preserved evidence after configuration is fixed.
