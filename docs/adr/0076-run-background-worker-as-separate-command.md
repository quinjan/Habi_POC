# Run Background Worker As Separate Command

The Habi POC will run background source processing through a separate worker command rather than starting an automatic polling loop inside the FastAPI app. The API is responsible for creating queued Processing Jobs, while the worker explicitly claims and processes them, making local development, behavior tests, and frontend polling easier to reason about.
