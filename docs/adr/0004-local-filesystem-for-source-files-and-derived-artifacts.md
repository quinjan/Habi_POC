# Local Filesystem For Source Files And Derived Artifacts

The Habi POC will preserve original uploaded source files unchanged on the local filesystem and store file metadata, checksums, source submission records, processing status, evidence locators, and artifact references in Postgres. Derived artifacts such as extracted text, parsed tables, OCR output, thumbnails, and normalized evidence snippets will be stored separately from originals so parsing behavior can be inspected without altering evidence.

This keeps source evidence easy to inspect during a local POC, avoids bloating Postgres with large binary files, and still allows review and search responses to cite project-scoped evidence through database-backed locators.
