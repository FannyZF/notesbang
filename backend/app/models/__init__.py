"""Phase 0 SQLAlchemy models mirroring PRD §6 core tables.

Only tables needed for the Phase 0 DoD are fully implemented; the rest are
declared as placeholders so the schema is stable when later phases add them.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str] = mapped_column(String(255))
    plan_state: Mapped[str] = mapped_column(
        String(20), default="trial"
    )  # trial | active | subscriber
    measured_speed_cps: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # chars/words per second (PRD §4.4)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_on_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    locale: Mapped[str] = mapped_column(String(8), default="en")  # en | zh
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    entitlement: Mapped["Entitlement"] = relationship(
        back_populates="user", uselist=False
    )
    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False)


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_pages_limit: Mapped[int] = mapped_column(Integer, default=2)
    trial_regens_per_page: Mapped[int] = mapped_column(Integer, default=1)
    trial_regens_whole: Mapped[int] = mapped_column(Integer, default=1)
    trial_whole_regens_used: Mapped[int] = mapped_column(Integer, default=0)
    trial_page_regens_used: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="entitlement")


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)  # in points
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic lock

    user: Mapped[User] = relationship(back_populates="wallet")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # trial_credit|charge|topup|refund
    amount: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id"), unique=True, nullable=True
    )
    provider_event_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_format: Mapped[str] = mapped_column(String(16))  # pptx | pdf | ...
    source_key: Mapped[str] = mapped_column(String(255))  # object storage key
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    # Generation settings (Phase 1 consumes these).
    target_minutes: Mapped[int] = mapped_column(Integer, default=10)
    note_mode: Mapped[str] = mapped_column(String(10), default="script")
    # Generation settings (Phase 1).
    style: Mapped[str] = mapped_column(String(32), default="business")
    custom_scenario: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(String(255), default="通用")
    persona: Mapped[str] = mapped_column(String(120), default="我/汇报人")
    output_lang: Mapped[str] = mapped_column(String(32), default="跟随")
    transitions: Mapped[bool] = mapped_column(Boolean, default=True)
    data_fidelity: Mapped[bool] = mapped_column(Boolean, default=True)
    speed_source: Mapped[str] = mapped_column(String(16), default="default")
    speed_cps: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_mode: Mapped[str] = mapped_column(String(16), default="full")  # full | fast
    vision_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    style_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("style_profiles.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    pages: Mapped[list["Page"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Page.ord"
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="未分节")
    ord: Mapped[int] = mapped_column(Integer, default=0)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id"), nullable=True
    )
    ord: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    image_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note_text: Mapped[str] = mapped_column(Text, default="")
    note_mode: Mapped[str] = mapped_column(String(10), default="script")
    weight: Mapped[float] = mapped_column(default=1.0)
    target_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="parsed")
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic lock

    project: Mapped[Project] = relationship(back_populates="pages")


class PageRevision(Base):
    __tablename__ = "page_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), index=True)
    note_text: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(16), default="system")  # user|system
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    type: Mapped[str] = mapped_column(String(24))  # parse|generate_*|export|...
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    phase: Mapped[str] = mapped_column(String(64), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    charge_amount: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    page_id: Mapped[int | None] = mapped_column(ForeignKey("pages.id"), nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_est: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ApiSession(Base):
    __tablename__ = "api_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PricingConfig(Base):
    __tablename__ = "pricing_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))


class Subscription(Base):
    """Placeholder for Phase 3 subscription support (PRD §2.2)."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(32), default="")
    plan_code: Mapped[str] = mapped_column(String(64), default="")
    renews_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StyleSample(Base):
    __tablename__ = "style_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    profile_text: Mapped[str] = mapped_column(Text, default="")
    profile_json: Mapped[str] = mapped_column(Text, default="{}")
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ==================== Content scoring product (pivot) ====================


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    source_format: Mapped[str] = mapped_column(String(16), default="paste")  # docx|txt|md|paste
    platform: Mapped[str] = mapped_column(String(24), default="auto")
    content: Mapped[str] = mapped_column(Text, default="")
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(8), default="")  # detected zh|en|...
    consent_improve: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    rubric_version: Mapped[str] = mapped_column(String(32), default="v1")
    platform: Mapped[str] = mapped_column(String(24), default="")
    overall_score: Mapped[float] = mapped_column(default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(64), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_est: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DimensionScore(Base):
    __tablename__ = "dimension_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    key: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(120), default="")
    band: Mapped[int] = mapped_column(Integer, default=0)  # 1..5
    score: Mapped[int] = mapped_column(Integer, default=0)  # mapped from band
    weight: Mapped[float] = mapped_column(default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    suggestions_json: Mapped[str] = mapped_column(Text, default="[]")


class Rewrite(Base):
    __tablename__ = "rewrites"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("analyses.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="full")  # full|title|hook|section
    content: Mapped[str] = mapped_column(Text, default="")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("analyses.id"), nullable=True
    )
    target_type: Mapped[str] = mapped_column(String(16), default="analysis")
    target_ref: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(24), default="")  # accepted|rejected|useful|not_useful
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CorpusFeature(Base):
    __tablename__ = "corpus_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    platform: Mapped[str] = mapped_column(String(24), default="")
    features_json: Mapped[str] = mapped_column(Text, default="{}")
    outcome_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_daily_usage"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD (UTC)
    count: Mapped[int] = mapped_column(Integer, default=0)
