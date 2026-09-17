# NotesBang — Operations Runbook

## Stack
`docker compose` runs: Postgres, Redis, API (FastAPI), Celery worker,
Celery beat, Next.js web, Caddy (HTTP/HTTPS reverse proxy). Set `PUBLIC_ORIGIN`,
`HTTP_PORT`, `SITE_ADDRESS` and secrets in `.env` (see `.env.example`).

Object storage (MinIO/S3) and slide rendering are **not** part of the
content-scoring product, so the stack runs with `STORAGE_BACKEND=local` and no
MinIO service.

### Public port (default 8088)
Caddy publishes **`HTTP_PORT` (default 8088) → container :80**. With the default
`SITE_ADDRESS=:80` it serves plain HTTP for any host, so the app is reachable at
`http://<server-ip>:8088`. For a real domain with automatic HTTPS set:

```env
PUBLIC_ORIGIN=https://notesbang.example.com
SITE_ADDRESS=notesbang.example.com
HTTP_PORT=80
HTTPS_PORT=443
```

`PUBLIC_ORIGIN` feeds `APP_BASE_URL` / `PUBLIC_WEB_URL` (email links) and the
frontend's `NEXT_PUBLIC_API_BASE` (`<PUBLIC_ORIGIN>/api`) — it must be the URL
users actually open, or verification links will be unreachable. Changing it
requires rebuilding the web image (`docker compose up -d --build web`).

## Server sizing

The LLM calls are network-bound; the real resource cost is **LibreOffice
headless rendering** (PPTX→PDF), which is CPU/RAM heavy (~300–500 MB per
process). Everything else is light.

| Tier | vCPU | RAM | Disk | Notes |
|---|---|---|---|---|
| Demo / very low traffic | 2 | 4 GB (+2 GB swap) | 40 GB SSD | `worker --concurrency=1..2`, or `RENDER_SLIDES=false` |
| Recommended launch | 4 | 8 GB (+2–4 GB swap) | 80 GB SSD | `worker --concurrency=2..3` |
| Growth | 8 | 16 GB | 160 GB+ | separate worker host; managed Postgres/Redis/S3 |

Per-service RAM (rough): Postgres 200–500 MB, Redis ~50 MB,
API 200–400 MB, worker 300–400 MB, beat ~100 MB,
Next.js standalone 150–300 MB, Caddy ~30 MB.

Storage: documents and analyses live in Postgres; uploads are stored on the
API/worker disk (`STORAGE_DIR`). Back up Postgres; nothing else needs mirroring.

Rules of thumb:
- Set Celery concurrency from RAM (2 on 4 GB, 3–4 on 8 GB); LibreOffice spikes.
- `RENDER_SLIDES=false` removes most CPU/RAM cost (no thumbnails/vision).
- Web/API are stateless (rate limiting via Redis) → scale horizontally;
  scale workers separately, they dominate CPU.
- OS: Ubuntu 22.04/24.04 LTS + Docker & Compose v2; expose only `HTTP_PORT`
  (default 8088), `HTTPS_PORT` (if using a domain) and SSH.
- Prefer servers with good network proximity to the LLM provider.

## First deploy
```bash
cp .env.example .env      # fill PUBLIC_ORIGIN, DEEPSEEK_API_KEY, ADMIN_TOKEN, SMTP_*, passwords
docker compose up -d --build
```
The API container runs `alembic upgrade head` on start (`RUN_MIGRATIONS=true`).

## Migrations
```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "change"
docker compose exec api alembic downgrade -1
```

## Backups & restore
- **Postgres** (the only stateful store): `docker compose exec postgres pg_dump -U notesbang notesbang > backup.sql`
  Restore: `cat backup.sql | docker compose exec -T postgres psql -U notesbang notesbang`

## Retention / housekeeping
Celery beat runs `jobs.retention_cleanup` daily (purges local upload artifacts
and stale data older than `RETENTION_DAYS`). Trigger manually:
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$PUBLIC_ORIGIN/api/admin/maintenance/cleanup?ttl_days=30"
```

## Observability
- Structured JSON logs on stdout (`docker compose logs -f api`).
- `GET /metrics` (Prometheus) — scrape via your monitoring.
- Optional Sentry via `SENTRY_DSN`.

## Scaling
- Increase `celery worker` replicas for analysis throughput.
- Rate limiting uses Redis (multi-instance safe).
- Web/API are stateless; Postgres and Redis hold all shared state.

## Incident basics
1. Check `docker compose ps` and `logs`.
2. API down? `docker compose restart api`; check migrations.
3. Stuck jobs: restarting the API marks stale `queued/running` jobs failed
   (`STALE_JOB_RESET`); users can regenerate.
4. Suspected secret leak: rotate `DEEPSEEK_API_KEY`, `ADMIN_TOKEN`, SMTP and
   DB passwords, then `docker compose up -d` to reload.
