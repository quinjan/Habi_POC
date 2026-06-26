# Modular Monolith FastAPI Backend

The Habi POC backend will be a modular monolith: one FastAPI application process organized into clear backend modules for projects, sources, processing, extraction, review, importing, memory, evidence, taxonomy, and search. This keeps domain boundaries visible in code without introducing microservices or distributed operations during the local POC.

The in-process worker loop for Postgres-backed processing jobs can live inside the backend unless real scaling pressure appears. Separate services or external workers can be introduced later if processing throughput, deployment topology, or reliability requirements outgrow the POC shape.
