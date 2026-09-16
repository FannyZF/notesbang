"""Rubric loading + rendering (platform-specific, bilingual).

Scoring is ordinal (bands 1..5); the code maps bands to fixed scores so the
model never invents numbers and results stay comparable across samples.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import get_settings

_RUBRIC_DIR = Path(__file__).resolve().parents[1] / "llm" / "rubrics"


@dataclass
class Dimension:
    key: str
    label_zh: str
    label_en: str
    definition_zh: str
    definition_en: str
    bands: dict


@dataclass
class Platform:
    key: str
    label_zh: str
    label_en: str
    weights: dict
    norms_zh: str
    norms_en: str
    limits: dict


@dataclass
class Rubric:
    version: str
    band_scores: dict
    dimensions: list[Dimension]
    platforms: dict


@lru_cache
def load_rubric() -> Rubric:
    path = _RUBRIC_DIR / f"rubric_{get_settings().rubric_version}.yaml"
    if not path.exists():
        path = _RUBRIC_DIR / "rubric_v1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    dims = [
        Dimension(
            key=d["key"],
            label_zh=d["label"]["zh"],
            label_en=d["label"]["en"],
            definition_zh=d["definition"]["zh"],
            definition_en=d["definition"]["en"],
            bands=d["bands"],
        )
        for d in data["dimensions"]
    ]
    platforms = {
        key: Platform(
            key=key,
            label_zh=val["label"]["zh"],
            label_en=val["label"]["en"],
            weights=val["weights"],
            norms_zh=val["norms"]["zh"],
            norms_en=val["norms"]["en"],
            limits=val.get("limits", {}),
        )
        for key, val in data["platforms"].items()
    }
    return Rubric(
        version=data.get("version", "v1"),
        band_scores={int(k): int(v) for k, v in data["band_scores"].items()},
        dimensions=dims,
        platforms=platforms,
    )


def band_to_score(band: int) -> int:
    return load_rubric().band_scores.get(int(band), 60)


def get_platform(key: str) -> Platform:
    rubric = load_rubric()
    return rubric.platforms.get(key) or rubric.platforms["auto"]


def platform_label(key: str, lang: str) -> str:
    p = get_platform(key)
    return p.label_zh if lang.startswith("zh") else p.label_en


def render_rubric_blocks(platform_key: str, lang: str) -> str:
    """Human-readable rubric text injected into the scoring prompt."""
    zh = lang.startswith("zh")
    rubric = load_rubric()
    platform = get_platform(platform_key)
    blocks: list[str] = []
    for dim in rubric.dimensions:
        weight = platform.weights.get(dim.key, 0)
        label = dim.label_zh if zh else dim.label_en
        definition = dim.definition_zh if zh else dim.definition_en
        lines = [f"维度 {dim.key}｜{label}｜权重 {weight:.2f}", f"说明：{definition}", "档位："]
        for band in sorted(dim.bands):
            info = dim.bands[band]
            anchor = info["anchor"]["zh" if zh else "en"]
            example = info["example"]["zh" if zh else "en"]
            lines.append(f"  {band}档：{anchor}｜示例：{example}")
        blocks.append("\n".join(lines))
    norms = platform.norms_zh if zh else platform.norms_en
    blocks.append(f"平台规范：{norms}")
    return "\n\n".join(blocks)


def weights_for(platform_key: str) -> dict:
    return get_platform(platform_key).weights
