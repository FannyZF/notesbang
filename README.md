# NotesBang — monorepo

AI speaker notes generator. Product/business requirements live in
[`docs/PRD.md`](docs/PRD.md). Operations guide: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Repository layout

```
backend/    FastAPI + SQLAlchemy (Python 3.12+)
frontend/   Next.js (App Router, TypeScript + Tailwind)
docs/       PRD + design docs
docker-compose.yml   optional infra (postgres/redis/minio) + api image
```

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 0 | monorepo scaffold, email-verified auth, PPTX parse + preview, trial (≤2 pages) & export lock, mock top-up + wallet/ledger | **done (backend tests passing)** |
| 1 | LLM gateway (mock/deepseek), dual-form prompts (script/cue), global outline pass, sequential per-page generation, length allocator + char fit, /plan preview, whole & single-page regenerate, trial budget & idempotent charging, speech rate endpoint | **backend done (18 tests passing)** |
| 2 | real export (PPTX notes write-back overwrite/merge + Word + PDF), project summary, page removal/editing (optimistic + revision backup), structure save, review heuristics, async job executor + polling | **done (24 tests passing)** |
| 3 | style-profile extraction + user library (samples/create/list/delete + prompt injection), billing webhook (idempotent settlement), mock subscription (plan_state + subscriptions table), usage/cost report | **done backend (28 tests passing); real MoR adapter + profile/subscribe UI pending** |

## Run locally (fast path — no Docker needed)

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- Default DB is `sqlite:///./spekernotes.db` (auto-created on startup).
- `MAIL_DRIVER=console` prints the email-verification link to stdout. In the
  scaffold UI the link is auto-consumed after registration (dev direct-through).

Open API docs: http://localhost:8000/docs  ·  Health: http://localhost:8000/healthz

### Frontend

```powershell
cd frontend
npm install
npm run dev   # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE` if the API is not at `http://localhost:8000/api`.

### Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Docker option (postgres + redis + minio + api)

```powershell
docker compose up --build
```

Then point `DATABASE_URL` at the postgres service (see `.env.example`).
Redis/MinIO are provisioned for later phases (queues, object storage).

## Local production-mode deploy (one command)

Builds a production frontend and starts FastAPI + `next start` without file
watching (mock LLM by default; set `$env:DEEPSEEK_API_KEY` first for the real
model).

```powershell
.\deploy-local.ps1          # ports: API 8000, Web 3000 (mock)
.\stop-local.ps1            # stop both servers
```

Logs: `%TEMP%\opencode\sn-*.log`. Admin console token defaults to
`dev-admin-secret` unless `$env:ADMIN_TOKEN` is set (console at `/admin`).

## Mock payment

Phase 0 uses `billing/providers/mock` style top-up (`POST /api/billing/topup`)
so the trial → balance → per-page charge loop is testable without a real
provider. Real MoR/PayPal integration is scheduled for Phase 3 (PRD §2.4).

## Key Phase 0 API flows

1. `POST /api/auth/register` → verify link → `GET /api/auth/verify` → login.
2. `POST /api/projects` (`.pptx`) → parsed page preview; trial caps at 2 pages.
3. `GET /api/billing/entitlements` → `export_locked` until balance > 0.
4. `POST /api/billing/topup` → wallet credited (ledger row written).
5. `POST /api/projects/{id}/export` → `402 EXPORT_LOCKED` (trial) / `501` (paid, Phase 2).

## Production hardening (P0/P1 — done)

- **Migrations**: Alembic (`backend/alembic`), run `alembic upgrade head`
  (API container does this automatically on start).
- **Storage**: object storage abstraction (`STORAGE_BACKEND=local|s3`) with
  MinIO/S3 support; local disk fallback for dev/tests.
- **Queue**: Celery + Redis (`TASK_BACKEND=celery`), worker + beat containers;
  thread pool remains the dev default. Rate limiting uses Redis when configured.
- **Observability**: JSON logs + `X-Request-ID`, optional Sentry, Prometheus
  `/metrics`.
- **Compliance**: account deletion (`DELETE /api/auth/account`), data export
  (`GET /api/auth/export`), retention TTL cleanup (`RETENTION_DAYS`, Celery beat
  or `POST /api/admin/maintenance/cleanup`), Privacy Policy page.
- **Payments**: provider framework (`billing/providers/*`, `PAYMENT_PROVIDER`);
  mock completes offline, real MoR adapter slot ready.
- **Quality**: 4-stage generation + whole-deck consistency pass; slide image
  rendering + thumbnails + budgeted vision (needs LibreOffice, `RENDER_SLIDES`).
- **Admin**: user search, points adjust/refund, plan override, ban/unban
  (`/admin`, `ADMIN_TOKEN`), notification preferences.
- **Deploy**: full `docker-compose` (postgres, redis, minio, api, worker, beat,
  web, caddy auto-HTTPS) + GitHub Actions CI.

## Key Phase 1 API flows

1. `PUT /api/projects/{id}/settings` — style / scenario / note_mode / duration / speed.
2. `POST /api/projects/{id}/plan` — per-page target allocation preview.
3. `POST /api/projects/{id}/generate` — sequential whole-deck generation (outline
   → per-page rolling context) and then charges / consumes the trial budget.
4. `POST /api/projects/{id}/pages/{page}/regenerate` — single-page regeneration.
5. `GET /api/speech/sample` + `POST /api/speech/measure` — fixed-sample reading
   speed; set `speed_source: manual` + `speed_cps` to override.

## Phase 2 notes

- **Async**: set `EXEC_ASYNC=true` so `POST .../generate` and
  `.../pages/{id}/regenerate` return `status: queued`; poll
  `GET /api/projects/{id}/jobs` until `succeeded|failed`. Default `false`
  executes inline so tests and simple local dev stay simple.
- **Editing**: `PUT /api/projects/{id}/pages/{pid}` (note_text/weight/mode,
  `expected_version` for optimistic locking; every overwrite backs up to
  `page_revisions`). `PUT /api/projects/{id}/structure` replaces sections.
- **Review**: `POST /api/projects/{id}/review` runs local consistency heuristics
  (empty notes, duplicated openings, near-duplicate pages).
- **Export formats**: `?fmt=pptx|docx|pdf`. PPTX write-back honours
  `strategy=overwrite|merge`. Exports are locked (402) until the user tops up.
- DeepSeek calibration report: `docs/calibration_deepseek_report.md`.

## Phase 3 notes

- **Style profiles** (user-level library): `POST /users/me/styles/samples`,
  `POST /users/me/styles` (LLM extraction; mock fallback offline), list/delete.
  Attach via `PUT /api/projects/{id}/settings` `{style_profile_id}`; a profile
  overrides the preset style block during generation.
- **Provider webhooks**: `POST /api/billing/webhook` settles
  `{provider,event_id,kind:topup|subscription,amount,currency,user_email}`
  idempotently on `event_id` (retry-safe). Mock subscribe:
  `POST /api/billing/subscribe {plan_code,amount}` activates `plan_state` +
  `subscriptions`. Real MoR adapters (FastSpring/Paddle/…) only need to verify
  their signature and map their payload onto this canonical shape.
- **Usage/cost report**: `GET /api/billing/report` (pages generated, LLM cost,
  top-ups vs charges, balance, project count).
- Pending Phase-3 UI: style manager and subscribe/billing page in the Next.js
  app (backend/API are complete and covered by tests).

## DeepSeek calibration (done — see docs/calibration_deepseek_report.md)

```powershell
$env:DEEPSEEK_API_KEY="sk-..."   # env only, never committed
$env:LLM_PROVIDER="deepseek"
python -m scripts.deepseek_calibrate   # from backend/
```

Findings (6-page zh deck, deepseek-v4-flash): outline ~8.6s, ~10s/page, ~$0.011
per deck; raw outputs run short (−15~−22%), so the deterministic char fitter is
required. Speech defaults kept at CN 3.3 chars/s (~200/min, pacing 0.85 →
~168 effective/min) and EN 2.5 wps (~150 wpm); calibrate with real `POST
/speech/measure` recordings later.

> LLM_PROVIDER defaults to `mock` (offline deterministic). Set
> `LLM_PROVIDER=deepseek` and `DEEPSEEK_API_KEY` to use the real model; set
> `MAIL_DRIVER=console` still prints verification links to the terminal.
