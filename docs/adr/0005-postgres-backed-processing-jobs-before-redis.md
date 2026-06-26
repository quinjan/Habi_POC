# Postgres-Backed Processing Jobs Before Redis

The Habi POC will use a Postgres-backed processing job table with an in-process worker loop for source parsing, OCR, AI extraction, embedding, and review preparation instead of adding Redis or a distributed queue at the start. Postgres must already preserve durable source-processing history, statuses, errors, and review readiness, so using it as the POC job coordinator keeps the architecture observable and simple for a local single-user app.

Redis or another queue can be introduced later if multi-worker throughput, delayed retries, stateless app deployment, or multi-instance scaling becomes a real bottleneck. Until then, Postgres remains the durable source of truth for job state and the UI reads processing progress from the database.

API requests that start long-running work, such as file upload parsing, OCR, AI extraction, embedding, or review preparation, return quickly with source submission and processing job IDs. The frontend polls or refreshes job and batch status through the backend API, while quick review/import actions can remain synchronous when they do not run slow extraction work.
