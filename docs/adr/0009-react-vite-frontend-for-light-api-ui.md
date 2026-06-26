# React Vite Frontend For Light API UI

The Habi POC frontend will use React with Vite because the frontend is a light API-consuming interface and does not need server-side application logic. The UI focuses on project selection, Purchase Lines, Upload / Review, entity lists, evidence inspection, and Search, while FastAPI owns all data access, validation, processing, AI calls, import rules, and retrieval.

Using React/Vite keeps the frontend small and fast to iterate while preserving the backend API as the only contract for project-memory behavior.
