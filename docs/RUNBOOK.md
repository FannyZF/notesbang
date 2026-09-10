# NotesBang — Operations Runbook

## Stack
`docker compose` runs: Postgres, Redis, MinIO, API (FastAPI), Celery worker,
Celery beat, Next.js web, Caddy (auto-HTTPS). Set `DOMAIN` and secrets in `.env`
(see `.env.example`).

## First deploy
```bash
cp .env.example .env      # fill DOMAIN, DEEPSEEK_API_KEY, ADMIN_TOKEN, SMTP_*, passwords
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
- **Postgres**: `docker compose exec postgres pg_dump -U notesbang notesbang > backup.sql`
  Restore: `cat backup.sql | docker compose exec -T postgres psql -U notesbang notesbang`
- **MinIO**: mirror the bucket (mc / rclone) to off-host storage on a schedule.

## Retention / housekeeping
Celery beat runs `jobs.retention_cleanup` daily (purges slide images for
projects older than `RETENTION_DAYS`). Trigger manually:
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://$DOMAIN/api/admin/maintenance/cleanup?ttl_days=30"
```

## Observability
- Structured JSON logs on stdout (`docker compose logs -f api`).
- `GET /metrics` (Prometheus) — scrape via your monitoring.
- Optional Sentry via `SENTRY_DSN`.

## Scaling
- Increase `celery worker` replicas for generation throughput.
- Rate limiting uses Redis (multi-instance safe).
- Object storage is MinIO/S3, so web/API are stateless (except local disk logs).

## Incident basics
1. Check `docker compose ps` and `logs`.
2. API down? `docker compose restart api`; check migrations.
3. Stuck jobs: restarting the API marks stale `queued/running` jobs failed
   (`STALE_JOB_RESET`); users can regenerate.
4. Suspected secret leak: rotate `DEEPSEEK_API_KEY`, `ADMIN_TOKEN`, SMTP and
   DB passwords, then `docker compose up -d` to reload.
