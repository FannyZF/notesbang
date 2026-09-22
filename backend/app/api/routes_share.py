"""Shareable, read-only scorecards.

A signed-in user can publish one analysis as a public link. The payload is
sanitized: no user identity, no document id, and the original copy (plus the
evidence excerpts, which are substrings of it) is only included when the user
explicitly opts in.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_verified
from app.api.routes_documents import _analysis_out, _owned
from app.core import runtime
from app.core.security import new_token, token_digest
from app.db.base import get_db
from app.models import Analysis, Document, Share, User
from app.schemas import ShareIn

router = APIRouter(tags=["share"])


def _latest_analysis(db: Session, doc_id: int) -> Analysis | None:
    return (
        db.query(Analysis)
        .filter(Analysis.document_id == doc_id)
        .order_by(Analysis.id.desc())
        .first()
    )


def _active_share(db: Session, doc_id: int) -> Share | None:
    return (
        db.query(Share)
        .filter(Share.document_id == doc_id, Share.revoked.is_(False))
        .order_by(Share.id.desc())
        .first()
    )


def _share_url(db: Session, token: str) -> str:
    base = runtime.mail_config(db)["public_web_url"].rstrip("/")
    return f"{base}/s/{token}"


def _public_payload(db: Session, share: Share) -> dict:
    analysis = db.get(Analysis, share.analysis_id)
    doc = db.get(Document, share.document_id)
    if analysis is None or doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Share not found")
    lang = doc.language if doc.language in ("zh", "en") else "en"
    data = _analysis_out(db, analysis, lang)

    dimensions = []
    for d in data["dimensions"]:
        entry = {
            "key": d["key"],
            "label": d["label"],
            "band": d["band"],
            "score": d["score"],
            "weight": d["weight"],
            "rationale": d["rationale"],
            "suggestions": d["suggestions"],
            "evidence": d["evidence"] if share.include_content else [],
        }
        dimensions.append(entry)

    payload = {
        "platform": data["platform"],
        "archetype": getattr(doc, "archetype", "auto"),
        "lang": lang,
        "title": doc.title,
        "overall_score": data["overall_score"],
        "summary": data["summary"],
        "consensus": data["consensus"],
        "dimensions": dimensions,
        "experts": [
            {"key": e["key"], "label": e["label"], "overall": e["overall"]}
            for e in data["experts"]
        ],
        "created_at": data["created_at"],
        "include_content": share.include_content,
        "views": share.views,
    }
    if share.include_content:
        payload["content"] = doc.content
    return payload


@router.post("/documents/{doc_id}/share", status_code=201)
def create_share(
    doc_id: int,
    payload: ShareIn,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    analysis = _latest_analysis(db, doc.id)
    if analysis is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Analyze the document before sharing it",
            headers={"X-Error-Code": "NO_ANALYSIS"},
        )
    # Rotate: revoke previous links for this document, then issue a fresh token.
    db.query(Share).filter(
        Share.document_id == doc.id, Share.revoked.is_(False)
    ).update({"revoked": True}, synchronize_session=False)
    token = new_token()
    share = Share(
        token_digest=token_digest(token),
        user_id=user.id,
        analysis_id=analysis.id,
        document_id=doc.id,
        include_content=bool(payload.include_content),
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return {
        "token": token,
        "url": _share_url(db, token),
        "include_content": share.include_content,
    }


@router.get("/documents/{doc_id}/share")
def get_share(
    doc_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    share = _active_share(db, doc.id)
    if share is None:
        return {"shared": False, "url": None, "include_content": False, "views": 0}
    return {
        "shared": True,
        "url": None,  # the raw token is only returned on creation
        "include_content": share.include_content,
        "views": share.views,
        "created_at": share.created_at.isoformat() if share.created_at else None,
    }


@router.delete("/documents/{doc_id}/share")
def revoke_share(
    doc_id: int,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
):
    doc = _owned(db, doc_id, user)
    db.query(Share).filter(
        Share.document_id == doc.id, Share.revoked.is_(False)
    ).update({"revoked": True}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.get("/share/{token}")
def public_share(token: str, db: Session = Depends(get_db)):
    share = (
        db.query(Share)
        .filter(Share.token_digest == token_digest(token), Share.revoked.is_(False))
        .first()
    )
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Share not found")
    payload = _public_payload(db, share)
    share.views = (share.views or 0) + 1
    db.commit()
    payload["views"] = share.views
    return payload
