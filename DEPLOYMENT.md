# Deploying DetectivePM

Three services, each needing an account you own: PostgreSQL, the backend (API and worker), and the frontend. Nothing here has been deployed yet.

Expected cost: Supabase free tier, Render Starter at about $7/month per service, and Vercel Hobby free. Check current pricing before committing, and note Render's free plan has no background workers.

## 1. Push the repository

Create a private GitHub repository, then:

```bash
git remote add origin https://github.com/YOUR_USER/detectivePM.git
```

```bash
git push -u origin main
```

## 2. Create the database

1. Create a Supabase project and choose a region near your backend, such as Mumbai.
2. Copy the **connection pooler** URL in session mode. Direct connections on Supabase can be IPv6-only.
3. Keep it for `DATABASE_URL`.

## 3. Deploy the backend

**Render:** New > Blueprint > choose the repository. `render.yaml` creates `detectivepm-api` and `detectivepm-worker`.

Set these on both services:

| Variable | Value |
|---|---|
| `DATABASE_URL` | From step 2 |
| `ADMIN_API_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `FRONTEND_URL` | Your Vercel URL; update it after step 4 |
| `BACKEND_URL` | The Render API URL |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Optional |
| `GOOGLE_SHEETS_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` | Optional |

The API service runs migrations and syncs the registry on each start. Deploy it first, then the worker.

**Railway instead:** create two services from the repository. Both use the Dockerfile; set the worker's start command to `python -m backend.worker`.

**No paid worker available?** Set `RUN_SCHEDULER_IN_API=true` on the API and skip the worker. The lease still prevents overlap, but a sleeping instance stops the schedule.

Verify:

```bash
curl https://YOUR-API/api/health
```

Expect `"database":"connected"`.

## 4. Deploy the frontend

1. On Vercel, import the repository and set **Root Directory** to `frontend`.
2. Set `BACKEND_URL` to the Render API URL. It is read at build time, so changing it needs a redeploy.
3. Deploy, then set `FRONTEND_URL` on both Render services to the Vercel URL.

## 5. Verify the live system

The worker starts discovery about 30 seconds after boot if data is stale. To start it by hand:

```bash
curl -X POST https://YOUR-API/api/scraper/run -H "X-Admin-Key: YOUR_KEY" -H "Content-Type: application/json" -d "{}"
```

Then confirm:

- [ ] `/api/health` reports the database connected.
- [ ] `/api/scraper/status` shows `"state":"running"` for the scheduler.
- [ ] `/sources` shows healthy sources, and Adzuna shows "Needs credentials" unless configured.
- [ ] The dashboard shows jobs, and each filter narrows them.
- [ ] Export CSV downloads, and an Apply link opens the original posting.
- [ ] `/api/jobs?search=demo` returns none, and the logs show no secrets.

## Rollback

Each host keeps earlier deployments. Roll back there. Schema changes reverse with:

```bash
python -m alembic downgrade -1
```

Back up the database first.

## Migrating schema later

After changing `backend/models.py`:

```bash
python -m alembic revision --autogenerate -m "describe the change"
```

```bash
python scripts/export_openapi.py
```

Review the generated migration, then run `npm run types` in `frontend` if the API changed. Migrations apply on the next API start.
