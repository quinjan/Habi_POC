# Worker Supports Once And Loop Modes

The background worker command will support both a run-once mode and a continuous loop mode. Run-once mode lets tests and local debugging explicitly process currently queued jobs, while loop mode is used beside the API and frontend during normal POC use; both modes should share the same job-claiming and processing code.
