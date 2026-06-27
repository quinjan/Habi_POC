# Use Postgres Row Locking For Job Claiming

The background worker will claim queued Processing Jobs with Postgres row locking, such as `SELECT ... FOR UPDATE SKIP LOCKED`, before marking a job as processing. Even though the first worker processes jobs serially, safe claiming prevents duplicate processing, duplicate AI calls, and conflicting Review Batch creation if two worker commands are accidentally started.
