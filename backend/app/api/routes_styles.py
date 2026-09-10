"""Style samples + profiles management (PRD §4.8, user-level library)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_verified
from app.db.base import get_db
from app.llm.gateway import get_provider
from app.models import Project, StyleProfile, StyleSample, User
from app.schemas import (
    StyleProfileIn,
    StyleProfileOut,
    StyleSampleIn,
    StyleSampleOut,
)
from app.services.style_profiles import extract_profile

router = APIRouter(prefix="/users/me/styles", tags=["styles"])


def _samples_of(db: Session, user: User) -> list[StyleSample]:
    return (
        db.query(StyleSample)
        .filter(StyleSample.user_id == user.id)
        .order_by(StyleSample.id.desc())
        .all()
    )


@router.post("/samples", response_model=StyleSampleOut, status_code=201)
def add_sample(
    payload: StyleSampleIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    sample = StyleSample(user_id=user.id, title=payload.title, text=payload.text)
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/samples", response_model=list[StyleSampleOut])
def list_samples(
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    return _samples_of(db, user)


@router.delete("/samples/{sample_id}")
def delete_sample(
    sample_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    sample = (
        db.query(StyleSample)
        .filter(StyleSample.id == sample_id, StyleSample.user_id == user.id)
        .first()
    )
    if sample is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sample not found")
    db.delete(sample)
    db.commit()
    return {"ok": True}


@router.post("", response_model=StyleProfileOut, status_code=201)
def create_profile(
    payload: StyleProfileIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    samples = (
        db.query(StyleSample)
        .filter(
            StyleSample.user_id == user.id,
            StyleSample.id.in_(payload.sample_ids),
        )
        .all()
    )
    if not samples:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No valid samples",
            headers={"X-Error-Code": "NO_SAMPLES"},
        )
    profile_text, profile_json = extract_profile(
        get_provider(), [s.text for s in samples]
    )
    profile = StyleProfile(
        user_id=user.id,
        name=payload.name,
        profile_text=profile_text,
        profile_json=profile_json,
        sample_count=len(samples),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=list[StyleProfileOut])
def list_profiles(
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    return (
        db.query(StyleProfile)
        .filter(StyleProfile.user_id == user.id)
        .order_by(StyleProfile.id.desc())
        .all()
    )


@router.delete("/{profile_id}")
def delete_profile(
    profile_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(StyleProfile)
        .filter(StyleProfile.id == profile_id, StyleProfile.user_id == user.id)
        .first()
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Profile not found")
    # Detach projects that reference this profile before deleting it.
    db.query(Project).filter(Project.style_profile_id == profile_id).update(
        {Project.style_profile_id: None}
    )
    db.delete(profile)
    db.commit()
    return {"ok": True}
