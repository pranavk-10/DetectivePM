# DetectivePM — Implementation Plan

Audit date: 2026-11-07. Baseline commit tagged `pre-reconstruction`.

## 1. Existing architecture

| Layer | State at audit |
|---|---|
| Backend | FastAPI (5 files, ~900 lines), raw `sqlite3`, APScheduler started inside the API process |
| Data source | Playwright/requests against a logged-in-only LinkedIn search page, with a random mock generator as the fallback |
| Storage | One SQLite table `scraped_posts`, CSV export next to the database |
| Frontend | Next.js 14.0.4, Tailwind, Recharts; one page and four components |
| Tests / deployment | None |

## 2. Existing defects

Verified by reading the code, running `tsc`, and read-only database inspection.

### Backend
- `scrape_and_store()` ran synchronously in the startup hook, delaying boot.
- The scheduler lived inside the API process, so multiple instances would scrape in parallel, and manual runs had no overlap lock.
- `allow_origins=["*"]` with credentials, and no auth on POST routes.
- `post_id` was derived from the author's profile URL, so a second post by one author was dropped as a duplicate.
- `last_scrape_time` was `MAX(post.timestamp)`, not the last actual run.
- Empty scraper results raised nothing, so the `requests` fallback never ran.

### Frontend
- `/api` had no rewrite and no Next API routes, so every request hit port 3000 and returned 404.
- `MetricsCards`, `GenreChart` and `PostsTable` all received different props than they declared (8 `tsc` errors).
- `Post` was imported from `api.ts` but never exported; the table read `res.posts`/`res.total_pages`, which the API never returned.
- `role_type=All` produced a 422; `genre=All` matched no rows.
- `'users client'` directive typo; profile links used a slug as a URL.
- "Live Scraper Active" and "Fully Operational" were hardcoded.
- Next 14.0.4 is an old patch release with known security advisories.

### Database
- One denormalised table; no migrations, indexes, foreign keys, or provenance.
- Genre taken from the mock template rather than the company.

### Repository
- No git repository, and `.gitignore`'s bare `lib/` rule would have excluded `frontend/src/lib`. Fixed before the baseline commit.

## 3. Mock-data problems
- All 30 stored rows match the generator: every `account_id` is `linkedin_` + a hash of the name.
- Rows contain fabricated contacts attached to real companies, such as `hiring@stripe.com`.
- Random IDs mean each fallback adds more rows, and nothing in the UI marks them as fake.

## 4. Data-source limitations

- **LinkedIn** is not scraped. It requires login and automated collection is not authorised. LinkedIn links can only be added manually.
- **Many target companies have no public ATS API.** Google, Microsoft, Amazon, Flipkart, Swiggy, Razorpay, PhonePe and others use private systems. They stay in the registry as `pending_source` with a verified careers URL, and yield no jobs until an authorised source exists.
- **Board tokens collide with unrelated companies.** Live probing found `porter` (interior design on Greenhouse, nurse practitioners on Lever), `slice` (restaurant platform), `navi` (pilot software), `fi`, `eternal`, `hevo`, `remote` and `wise`. Tokens are only added after board identity is confirmed from the job text.
- **Entry-level India PM roles are rare at any moment.** An honest low count is the expected outcome.
- **Remotive** requires attribution and asks for infrequent calls, so it has a 6-hour minimum interval and always shows its source. Its `product` category is unreliable, so the role classifier does the real filtering.
- **Adzuna** covers India well but needs a free API key. The connector is implemented and reports `needs_credentials` until keys are set.

## 5. Proposed architecture

```
Sources ─► connectors ─► validate ─► geo + role + industry ─► dedupe ─► PostgreSQL ─► FastAPI ─► Next.js
(ATS, RSS, API, manual)                                                     ▲
                                 worker: discovery / verification / enrichment / maintenance
```

Key decisions:
- **One visible-listing predicate** (`backend/queries.py`) used by every list, metric, search and export path.
- **A database CHECK constraint** makes it impossible for a row to be `accepted` without `india_eligible = true` and `country_code = 'IN'`.
- **Rejected jobs are never stored.** Uncertain jobs go to `manual_review` with `india_eligible = false`.
- **A separate worker** owns the schedule. A database lease prevents overlap across instances, and heartbeats give the dashboard real scheduler state.
- **A connector per board.** Each ATS board is its own `sources` row, so health is reported per board and a failure is isolated.
- **Generated types.** TypeScript types come from the FastAPI OpenAPI document, and a test fails if they drift.
- **Same-origin frontend.** A Next rewrite proxies `/api/*` to the backend.
- **Admin auth by `X-Admin-Key`.** The key is never bundled into the frontend; an admin enters it in the browser for that session.

The optional LLM classifier and the Section 21 features are out of scope until the core pipeline is proven, so `LLM_API_KEY` is not in `.env.example`.

## 6. Implementation sequence

1. Audit, git baseline, this plan.
2. SQLAlchemy models, Alembic, mock removal, legacy cleanup with report.
3. India validator, role and industry classifiers.
4. Greenhouse, Lever, Ashby, careers-page, RSS, authorised API and manual connectors.
5. Company registry built from live probes.
6. Ingestion, dedupe, verification, recruiter enrichment.
7. Worker, API, auth, exports.
8. Frontend rebuilt on generated types.
9. Backend, frontend and end-to-end tests on real PostgreSQL with real data.
10. Dockerfile, worker config, Vercel config, docs, `TEST_REPORT.md`.
11. Deployment.

## 7. Deployment strategy

- **Database:** Supabase or another managed PostgreSQL. SQLite is refused when `ENVIRONMENT=production`.
- **API:** Docker service on Render or Railway. Migrations run before start.
- **Worker:** A second service from the same image. Hosts without paid workers can set `RUN_SCHEDULER_IN_API=true`; the lease still applies.
- **Frontend:** Vercel with `BACKEND_URL` set at build time.
- **Blocked on the owner:** This environment has no accounts or CLIs for these hosts, and creating accounts or entering credentials must be done by the owner. See `DEPLOYMENT.md`.
