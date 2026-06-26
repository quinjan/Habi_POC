# SQLAlchemy And Alembic For Persistence

The Habi POC backend will use SQLAlchemy for Postgres persistence and Alembic for schema migrations. The data model needs explicit relational structure for project isolation, review/import state, taxonomy, evidence links, memory records, type-specific tables, value history, and pgvector-backed retrieval, while migrations need to evolve safely as the POC schema changes.

SQLAlchemy should be used in an explicit, readable style so import rules, evidence requirements, and search behavior remain understandable rather than hidden behind overly magical ORM patterns.
