# OpenAI Portal Setup For Habi AI Extraction

This guide explains how to configure the OpenAI API side for the local Habi
Processing Job worker.

Habi uses the OpenAI API only from the backend worker. A ChatGPT or Codex Pro
subscription is not a runtime credential for this app. The worker needs an
OpenAI API key from the API platform.

## 1. Sign In To The API Platform

1. Open <https://platform.openai.com/>.
2. Sign in with the account or organization that should pay for Habi local API
   usage.
3. Confirm you are in the intended organization from the organization/project
   selector in the platform header.

## 2. Create Or Select A Project

1. Open organization settings: <https://platform.openai.com/settings/organization>.
2. Create or select a project for this local Habi POC.
3. Recommended project name:

   ```text
   Habi POC Local
   ```

Using a dedicated project keeps API keys, usage, rate limits, and budget controls
separate from other experiments.

## 3. Enable Billing Or Credits

1. Open billing overview:

   <https://platform.openai.com/settings/organization/billing/overview>

2. Add payment details or prepaid credits if the organization is not already
   billable.
3. Optional but recommended: configure a low monthly project budget before
   running local extraction tests.

If billing or credits are not active, the worker may start successfully but the
OpenAI request can fail at runtime. In that case Habi should mark the claimed
Processing Job as `failed` with the provider error.

## 4. Check Project Model Access And Limits

1. In organization settings, select the Habi project.
2. Open the project's `Limits` page.
3. Confirm the project can use the model configured for Habi:

   ```text
   gpt-5.4-nano
   ```

4. If needed, set conservative model rate limits for local development.

Habi defaults to `gpt-5.4-nano` when `OPENAI_MODEL` is not set.

## 5. Create A Project API Key

1. Open the API keys page:

   <https://platform.openai.com/api-keys>

2. Make sure the selected project is the Habi project.
3. Click `Create new secret key`.
4. Use a clear name:

   ```text
   habi-local-worker
   ```

5. Choose project-scoped permissions. For local development, either:
   - use the default project key permissions, or
   - use restricted permissions that allow model response creation.
6. Copy the key immediately. You will not be able to view the full secret again.

Do not commit the real API key to git and do not put it in frontend code. Habi
uses it only in the backend/worker container.

## 6. Put The Key In Local `.env`

Edit the repo-local `.env` file:

```env
OPENAI_API_KEY=sk-your-real-key-here
OPENAI_MODEL=gpt-5.4-nano
OPENAI_BASE_URL=
```

Notes:

- Leave `OPENAI_BASE_URL` empty for the default OpenAI API endpoint.
- Keep `.env.example` as placeholders only.
- Restart Docker Compose after changing `.env`; existing containers do not
  automatically reload changed environment variables.

## 7. Rebuild And Restart Docker Compose

Run from the repo root:

```powershell
docker compose down
docker compose up --build
```

The normal app stack starts Postgres, backend API, frontend, and the Processing
Job worker.

## 8. Confirm The Worker Is Running

Check all services:

```powershell
docker compose ps
```

Expected services:

```text
postgres
backend
frontend
worker
```

The worker runs continuously as part of `docker compose up`.

For focused debugging, you can still run a one-off worker command.

Process one queued job and exit:

```powershell
docker compose run --rm backend python -m backend.app.processing --once
```

Run an extra temporary worker loop:

```powershell
docker compose run --rm backend python -m backend.app.processing --loop
```

Expected behavior:

- Missing `OPENAI_API_KEY`: worker refuses to start before claiming jobs, and
  queued jobs stay `queued`.
- Valid config but OpenAI runtime failure: worker claims the job and marks it
  `failed` with a useful error message.
- Valid config and usable model response: worker creates reviewable extracted
  Purchase Line candidates.

## 9. Smoke Test From The UI

1. Open the frontend:

   <http://127.0.0.1:5173>

2. Select or create a Project Workspace.
3. Go to `Upload / Review`.
4. Submit one free-form Manual Source Entry, for example:

   ```text
   Bought 20 pcs PVC pipe from ABC Trading for PHP 1,500 on 2025-07-15.
   ```

5. In another terminal, run:

   ```powershell
   docker compose run --rm backend python -m backend.app.processing --once
   ```

6. Return to the UI and check the job status.

The successful path should move the Processing Job out of `queued` and into a
review-ready state with extracted candidates.

## 10. Troubleshooting

### Job Stays Queued

Most likely no worker is running, or the worker refused to start before claiming
the job because required OpenAI configuration is missing.

Run:

```powershell
docker compose run --rm backend python -m backend.app.processing --once
```

If you see `OPENAI_API_KEY is required`, update `.env`, restart containers, and
run the worker again.

### Job Fails With Authentication Error

Check that `.env` contains the same key you created in the platform:

```env
OPENAI_API_KEY=sk-...
```

Then restart Docker Compose.

### Job Fails With Billing Or Quota Error

Check:

- organization billing overview,
- project budget,
- project model limits,
- usage dashboard.

### Job Fails With Model Access Error

Confirm `OPENAI_MODEL` is set to a model available to the selected project. Habi
defaults to:

```env
OPENAI_MODEL=gpt-5.4-nano
```

## Official References

- OpenAI projects and project API keys:
  <https://help.openai.com/en/articles/9186755-managing-your-work-in-the-api-platform-with-projects>
- API key troubleshooting:
  <https://help.openai.com/en/articles/6882433-incorrect-api-key-provided>
- API key safety:
  <https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety>
- Billing and prepaid credits:
  <https://help.openai.com/en/articles/8264644-how-can-i-set-up-prepaid-billing>
- Usage dashboard:
  <https://help.openai.com/en/articles/10478918-api-usage-dashboard>
