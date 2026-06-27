# Local Development Setup

This guide runs Habi with Docker Compose:

- Postgres in Docker, with a persistent Docker volume.
- FastAPI backend in Docker on `http://127.0.0.1:8000`.
- React/Vite frontend in Docker on `http://127.0.0.1:5173`.

## Prerequisites

- Docker Desktop

## 1. Configure Local Environment

The app requires a local `.env` file. This repo includes a local-machine `.env` for this checkout and a template at `.env.example`.

If you need to recreate it, run this from the repo root:

```powershell
Copy-Item .env.example .env
```

For Docker Compose, the backend database URL uses the Compose service name:

```text
postgresql+psycopg://habi:habi_local_password@postgres:5432/habi_poc
```

## 2. Start the Whole App

```powershell
docker compose up --build
```

Compose starts Postgres, waits for it to become healthy, runs backend migrations, starts the FastAPI backend, and starts the Vite frontend.

Open:

```text
http://127.0.0.1:5173
```

Backend OpenAPI is available at:

```text
http://127.0.0.1:8000/docs
```

## 3. Check Service Status

```powershell
docker compose ps
```

The database data is stored in the named Docker volume:

```text
habi_postgres_data
```

## 4. Run Migrations Manually

The backend container runs migrations on startup. To run them manually:

```powershell
docker compose run --rm backend alembic -c backend/alembic.ini upgrade head
```

## 5. Regenerate Frontend API Types

After backend API changes:

```powershell
docker compose run --rm frontend npm run generate:api
```

## 6. Run Processing Worker

Process one queued job and exit:

```powershell
docker compose run --rm backend python -m backend.app.processing --once
```

Run the worker loop beside the API and frontend:

```powershell
docker compose run --rm backend python -m backend.app.processing --loop
```

## 7. Run Tests

Backend:

```powershell
docker compose run --rm backend pytest backend/tests -q
```

Frontend:

```powershell
docker compose run --rm frontend npm test
docker compose run --rm frontend npm run build
```

## 8. Stop Local Services

```powershell
docker compose down
```

Stop everything and delete the local database volume:

```powershell
docker compose down -v
```

Use `down -v` only when you intentionally want to erase local Habi database data.

## Troubleshooting

Show logs:

```powershell
docker compose logs -f
```

Rebuild containers after dependency changes:

```powershell
docker compose build --no-cache
```
