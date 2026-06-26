# OpenAPI Contracts From FastAPI For Frontend Types

The Habi POC will treat FastAPI's OpenAPI output, generated from Pydantic request and response models, as the API contract between backend and frontend. The React/Vite frontend should consume generated or shared TypeScript types and API client code from that contract rather than manually duplicating backend shapes.

This keeps the frontend light while reducing contract drift across project selection, source submission, processing status, candidate review, import, memory browsing, evidence inspection, and search responses.
