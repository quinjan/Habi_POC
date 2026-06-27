# Support Multiple Outstanding Jobs With Serial Worker

Habi will support multiple outstanding Processing Jobs in the UI and backend, allowing reviewers to submit several Manual Source Entries and browse each ready Review Batch independently. The first background worker implementation will still process one claimed job at a time, deferring parallel AI calls, worker concurrency settings, and rate-limit coordination until throughput becomes a proven need.
