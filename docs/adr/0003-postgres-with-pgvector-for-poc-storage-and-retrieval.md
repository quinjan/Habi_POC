# Postgres With pgvector For POC Storage And Retrieval

The Habi POC will use Postgres with pgvector as the primary database and semantic retrieval index instead of introducing a separate vector database. This keeps relational constraints, project isolation, review/import state, evidence links, JSONB flexibility, and vector similarity search in one durable store while avoiding extra infrastructure before the POC proves that AI parsing and evidence-backed search work.

A separate vector database can be reconsidered later if retrieval scale, latency, ranking features, or operational needs outgrow Postgres.
