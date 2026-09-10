"""Speech-rate endpoints (PRD §4.4): fixed sample text + timing.

Passage language selects the canonical sample (zh hanzi chars, en words) so
the measured pace is counted consistently with generation length rules.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_verified
from app.db.base import get_db
from app.models import User
from app.schemas import SpeedIn, SpeedOut, SpeechSampleOut
from app.services.speech import measure_speed, sample_chars_for, sample_for
from sqlalchemy.orm import Session

router = APIRouter(prefix="/speech", tags=["speech"])


@router.get("/sample", response_model=SpeechSampleOut)
def get_sample(
    user: User = Depends(require_verified),
    lang: str = Query(default="zh", pattern="^(zh|en)$"),
):
    return SpeechSampleOut(text=sample_for(lang), chars=sample_chars_for(lang))


@router.post("/measure", response_model=SpeedOut)
def measure(
    payload: SpeedIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    cps, per_min = measure_speed(db, user, payload.duration_ms, payload.lang)
    return SpeedOut(cps=cps, chars_per_minute=per_min, measured_cps=cps)
