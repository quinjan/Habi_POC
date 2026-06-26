# Run Backend Behavior Tests Against Postgres

Backend behavior tests will run against Postgres rather than SQLite. The POC depends on Postgres-specific persistence behavior for project isolation, JSON-backed source and candidate payloads, Processing Job lifecycle state, migrations, and later pgvector retrieval, so tests should exercise the same database engine used by local development and production-like POC runs even though setup is less lightweight than temporary SQLite files.
