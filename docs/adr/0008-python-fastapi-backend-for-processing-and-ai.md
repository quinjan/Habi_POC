# Python FastAPI Backend For Processing And AI

The Habi POC backend will use Python with FastAPI because the backend owns the core proof: source parsing, OCR coordination, spreadsheet/PDF handling, AI extraction, schema validation, embeddings, job processing, import rules, and retrieval. Python keeps the document-processing and AI orchestration work close to the strongest ecosystem while FastAPI provides explicit API contracts for the light frontend.

The frontend remains separate and communicates only through the backend API. Backend modules, not frontend code, own database access, file/artifact access, LLM calls, validation, job status, and project-memory rules.
