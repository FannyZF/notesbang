"""Pydantic request/response schemas (Phase 0 subset)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# ---------- auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterOut(BaseModel):
    id: int
    email: EmailStr
    email_verified: bool
    plan_state: str
    dev_verify_url: str | None = None  # returned only when MAIL_DRIVER=console
    message: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=8, max_length=128)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=8)
    new: str = Field(min_length=8, max_length=128)


class LoginOut(BaseModel):
    token: str
    user_id: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    email_verified: bool
    plan_state: str


# ---------- billing ----------
class TopupIn(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(default="USD", max_length=8)


class CheckoutIn(BaseModel):
    points: int = Field(gt=0, le=100_000)


class CheckoutOut(BaseModel):
    status: str  # completed | pending
    points: int
    checkout_url: str | None = None
    balance: int | None = None


class LedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    amount: int
    job_id: int | None
    provider_event_id: str | None
    note: str | None
    created_at: datetime


class WalletOut(BaseModel):
    balance: int
    currency: str
    ledger: list[LedgerOut]


class EntitlementOut(BaseModel):
    trial_used: bool
    trial_pages_limit: int
    export_locked: bool


# ---------- projects ----------
class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ord: int
    raw_text: str
    note_text: str
    note_mode: str
    weight: float
    status: str
    version: int


class PageSummary(BaseModel):
    ord: int
    chars: int


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    type: str
    target_id: int | None
    status: str
    progress: int
    phase: str | None = None
    error: str | None
    charge_amount: int
    created_at: datetime


class SummaryOut(BaseModel):
    project_id: int
    total_chars: int
    speed_cps: float
    est_minutes: float
    target_minutes: int
    pages: list[PageSummary]


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_format: str
    status: str
    target_minutes: int | None = 10
    note_mode: str | None = "script"
    style: str | None = "business"
    custom_scenario: str | None = ""
    audience: str | None = "General"
    persona: str | None = "I"
    output_lang: str | None = "auto"
    transitions: bool | None = True
    data_fidelity: bool | None = True
    speed_source: str | None = "default"
    speed_cps: float | None = None
    quality_mode: str | None = "full"
    running: bool = False
    style_profile_id: int | None = None
    pages: list[PageOut] = []
    created_at: datetime

    @model_validator(mode="after")
    def _fill_defaults(self):
        defaults = {
            "target_minutes": 10,
            "note_mode": "script",
            "style": "business",
            "custom_scenario": "",
            "audience": "General",
            "persona": "I",
            "output_lang": "auto",
            "transitions": True,
            "data_fidelity": True,
            "speed_source": "default",
            "quality_mode": "full",
        }
        for field_name, value in defaults.items():
            if getattr(self, field_name) is None:
                setattr(self, field_name, value)
        legacy_lang = {"跟随": "auto", "中文": "zh", "英文": "en"}
        if self.output_lang in legacy_lang:
            self.output_lang = legacy_lang[self.output_lang]
        return self


class ProjectSummary(BaseModel):
    id: int
    title: str
    source_format: str
    status: str
    page_count: int
    created_at: datetime


# ---------- Phase 1: generation ----------
class GenerationSettingsIn(BaseModel):
    """Partial update; only provided fields are applied."""

    target_minutes: int | None = Field(default=None, ge=1, le=240)
    note_mode: str | None = None  # script | cue
    style: str | None = None
    custom_scenario: str | None = None
    audience: str | None = None
    persona: str | None = None
    output_lang: str | None = None
    transitions: bool | None = None
    data_fidelity: bool | None = None
    speed_source: str | None = None  # default | manual | recording
    speed_cps: float | None = Field(default=None, gt=0, le=20)
    quality_mode: str | None = None  # full | fast
    style_profile_id: int | None = None


class PlanPage(BaseModel):
    ord: int
    page_id: int
    weight: float
    target_chars: int


class PlanOut(BaseModel):
    project_id: int
    total_units: int
    unit_name: str
    target_minutes: int
    speed_cps: float
    pages: list[PlanPage]


class GenerateOut(BaseModel):
    job_id: int
    project_id: int
    status: str
    updated_pages: int
    total_units: int
    mode: str
    charged_points: int


class SpeechSampleOut(BaseModel):
    text: str
    chars: int


class SpeedIn(BaseModel):
    duration_ms: int = Field(gt=0, le=300_000)
    lang: str = Field(default="zh", pattern="^(zh|en)$")


class SpeedOut(BaseModel):
    cps: float
    chars_per_minute: float
    measured_cps: float


# ---------- Phase 2: structure / page editing / review ----------
class PageUpdateIn(BaseModel):
    note_text: str | None = None
    weight: float | None = Field(default=None, gt=0.1, le=5.0)
    note_mode: str | None = None
    expected_version: int | None = None


class PageRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    note_text: str
    actor: str
    created_at: datetime


class RestoreIn(BaseModel):
    revision_id: int


class PageAssignIn(BaseModel):
    page_id: int
    ord: int = Field(ge=1)
    weight: float = Field(default=1.0, gt=0.1, le=5.0)


class SectionStructureIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    pages: list[PageAssignIn]


class StructureIn(BaseModel):
    sections: list[SectionStructureIn]


class StructureSectionOut(BaseModel):
    id: int
    name: str
    pages: list[int]


class StructureOut(BaseModel):
    sections: list[StructureSectionOut]


class ReviewIssue(BaseModel):
    severity: str  # info | warn
    message: str
    pages: list[int]


class ReviewOut(BaseModel):
    project_id: int
    clean: bool
    issues: list[ReviewIssue]


# ---------- Phase 3: style profiles / billing / reports ----------
class StyleSampleIn(BaseModel):
    title: str = Field(default="", max_length=120)
    text: str = Field(min_length=20, max_length=20_000)


class StyleSampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    text: str
    created_at: datetime


class StyleProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sample_ids: list[int] = Field(min_length=1, max_length=5)


class StyleProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    profile_text: str
    sample_count: int
    created_at: datetime


class WebhookIn(BaseModel):
    provider: str = Field(default="mock")
    event_id: str = Field(min_length=1)
    kind: str = Field(pattern="^(topup|subscription)$")
    amount: int = Field(gt=0)
    currency: str = Field(default="USD", max_length=8)
    user_email: str
    plan_code: str | None = None


class SubscribeIn(BaseModel):
    plan_code: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0)


class UsageReportOut(BaseModel):
    user_id: int
    generated_pages: int
    generation_cost_usd: float
    topups_points: int
    charges_points: int
    balance: int
    projects: int
