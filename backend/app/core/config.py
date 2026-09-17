"""Application settings loaded from environment variables.

Phase 0 keeps the surface small; no secrets are hardcoded. Secrets must be
injected via env vars / secret manager only (see PRD §14.7.3).
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "NotesBang API")
        self.environment = os.getenv("ENVIRONMENT", "development")
        # Phase 0 default is SQLite so the scaffold runs without infra.
        # Postgres URL can be provided (e.g. postgresql+psycopg://...) later.
        self.database_url = os.getenv(
            "DATABASE_URL", "sqlite:///./spekernotes.db"
        )
        self.mail_driver = os.getenv("MAIL_DRIVER", "console")  # console | smtp
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", "")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        # Origin used to build links inside emails. /verify and /reset are
        # frontend pages, so the default points at the web server, not the API.
        self.app_base_url = os.getenv("APP_BASE_URL", "http://localhost:3000")
        self.token_ttl_hours = int(os.getenv("TOKEN_TTL_HOURS", "24"))

        # Product knobs (see PRD §17 pending items; defaults are placeholders).
        self.page_limit = int(os.getenv("PAGE_LIMIT", "80"))
        self.trial_pages_limit = int(os.getenv("TRIAL_PAGES_LIMIT", "2"))
        self.price_per_page_points = int(
            os.getenv("PRICE_PER_PAGE_POINTS", "1")
        )
        # Server-side abuse limits (rate limiting).
        self.rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        self.trust_proxy = os.getenv("TRUST_PROXY", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        self.register_ip_per_hour = int(os.getenv("REGISTER_IP_PER_HOUR", "10"))
        self.register_ip_burst_per_min = int(os.getenv("REGISTER_IP_BURST_PER_MIN", "6"))
        self.login_ip_per_5min = int(os.getenv("LOGIN_IP_PER_5MIN", "15"))
        self.verify_ip_per_hour = int(os.getenv("VERIFY_IP_PER_HOUR", "60"))
        self.upload_user_per_hour = int(os.getenv("UPLOAD_USER_PER_HOUR", "30"))
        self.admin_token = os.getenv("ADMIN_TOKEN", "")
        # Payment provider: "mock" (dev) or a real MoR adapter name.
        self.payment_provider = os.getenv("PAYMENT_PROVIDER", "mock")
        self.fastspring_api_key = os.getenv("FASTSPRING_API_KEY", "")
        self.fastspring_store_id = os.getenv("FASTSPRING_STORE_ID", "")
        self.fastspring_webhook_secret = os.getenv("FASTSPRING_WEBHOOK_SECRET", "")
        self.notify_on_complete = os.getenv("NOTIFY_ON_COMPLETE", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        self.public_web_url = os.getenv("PUBLIC_WEB_URL", "http://localhost:3000")
        # Object storage (MinIO/S3 compatible). "local" keeps files on disk
        # (dev/tests); "s3" uses boto3 against S3_ENDPOINT.
        self.storage_backend = os.getenv("STORAGE_BACKEND", "local")  # local | s3
        self.storage_dir = os.getenv("STORAGE_DIR", "storage")
        self.s3_endpoint = os.getenv("S3_ENDPOINT", "")
        self.s3_bucket = os.getenv("S3_BUCKET", "notesbang")
        self.s3_access_key = os.getenv("S3_ACCESS_KEY", "")
        self.s3_secret_key = os.getenv("S3_SECRET_KEY", "")
        self.s3_region = os.getenv("S3_REGION", "us-east-1")
        self.s3_secure = os.getenv("S3_SECURE", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        # Slide rendering + multimodal vision.
        self.render_slides = os.getenv("RENDER_SLIDES", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        self.soffice_path = os.getenv("SOFFICE_PATH", "")
        self.vision_enabled = os.getenv("VISION_ENABLED", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        self.vision_max_pages = int(os.getenv("VISION_MAX_PAGES", "20"))
        self.retention_days = int(os.getenv("RETENTION_DAYS", "30"))
        # Content-scoring product knobs.
        self.content_max_chars = int(os.getenv("CONTENT_MAX_CHARS", "3000"))
        self.free_daily_limit = int(os.getenv("FREE_DAILY_LIMIT", "3"))
        self.rubric_version = os.getenv("RUBRIC_VERSION", "v1")
        self.scoring_cache_enabled = os.getenv(
            "SCORING_CACHE_ENABLED", "true"
        ).lower() in ("1", "true", "yes")
        self.export_enabled = os.getenv("EXPORT_ENABLED", "false").lower() in (
            "1",
            "true",
            "yes",
        )

        # LLM gateway (Phase 1). "mock" is the default so the pipeline runs
        # offline without an API key; set LLM_PROVIDER=deepseek to go live.
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock")  # mock | deepseek
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.deepseek_vision_model = os.getenv(
            "DEEPSEEK_VISION_MODEL", "deepseek-v4-flash-vision-exp"
        )
        # Indicative per-million-token prices for cost estimation only.
        self.cost_input_per_m = float(os.getenv("COST_INPUT_PER_M", "0.27"))
        self.cost_output_per_m = float(os.getenv("COST_OUTPUT_PER_M", "1.10"))
        # Display rate for converting estimated LLM cost (USD) to CNY.
        self.usd_to_cny = float(os.getenv("USD_TO_CNY", "7.2"))

        # Length/speech defaults (PRD §4.4 placeholders).
        self.default_speed_cps_cn = float(os.getenv("DEFAULT_SPEED_CPS_CN", "3.3"))
        self.default_speed_cps_en = float(os.getenv("DEFAULT_SPEED_CPS_EN", "2.5"))
        self.pacing_factor = float(os.getenv("PACING_FACTOR", "0.85"))
        self.char_tolerance = float(os.getenv("CHAR_TOLERANCE", "0.15"))
        self.trial_regen = os.getenv("TRIAL_REGEN", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        # Phase 2 async execution: false runs generate/regen inline (tests and
        # simple local dev); true enqueues on a local thread executor. A real
        # Celery/Redis deployment can be layered on later (PRD §15).
        self.exec_async = os.getenv("EXEC_ASYNC", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        self.async_max_workers = int(os.getenv("ASYNC_MAX_WORKERS", "2"))
        self.job_poll_interval_s = float(os.getenv("JOB_POLL_INTERVAL_S", "1"))
        # Queue backend: "thread" (dev/tests) or "celery" (Redis broker).
        self.task_backend = os.getenv("TASK_BACKEND", "thread")  # thread | celery
        self.redis_url = os.getenv("REDIS_URL", "")
        self.celery_eager = os.getenv("CELERY_EAGER", "false").lower() in (
            "1",
            "true",
            "yes",
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
