"""Persist a committee analysis (analysis + aggregates + per-expert scores)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import Analysis, DimensionScore, Document, ExpertScore


def save_analysis(db: Session, doc: Document, result) -> Analysis:
    analysis = Analysis(
        document_id=doc.id,
        rubric_version=result.rubric_version,
        platform=result.platform,
        overall_score=result.overall_score,
        summary=result.summary,
        consensus_json=json.dumps(result.consensus, ensure_ascii=False),
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_est=result.cost_est,
    )
    db.add(analysis)
    db.flush()
    for d in result.dimensions:
        db.add(
            DimensionScore(
                analysis_id=analysis.id,
                key=d["key"],
                label=d["label"],
                band=d["band"],
                score=d["score"],
                spread=d.get("spread", 0.0),
                weight=d["weight"],
                rationale=d["rationale"],
                evidence_json=json.dumps(d["evidence"], ensure_ascii=False),
                suggestions_json=json.dumps(d["suggestions"], ensure_ascii=False),
            )
        )
    for expert in result.experts:
        for d in expert["dimensions"]:
            db.add(
                ExpertScore(
                    analysis_id=analysis.id,
                    expert=expert["key"],
                    key=d["key"],
                    band=d["band"],
                    score=d["score"],
                    rationale=d["rationale"],
                    evidence_json=json.dumps(d["evidence"], ensure_ascii=False),
                    suggestions_json=json.dumps(d["suggestions"], ensure_ascii=False),
                )
            )
    doc.status = "analyzed"
    db.commit()
    db.refresh(analysis)
    return analysis
