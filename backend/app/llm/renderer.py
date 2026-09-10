"""Jinja-based prompt rendering (PRD §4.9).

Style blocks are stored as whole ready-made texts and inlined, keeping the
templates simple and reviewable. Rendered prompts are deterministic given the
same inputs, which the snapshot-regression tests rely on.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2
import yaml

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_MODES_DIR = _PROMPT_DIR / "modes"
_STYLES_DIR = _PROMPT_DIR / "styles"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_MODES_DIR)),
    autoescape=False,
    keep_trailing_newline=True,
)


def load_style(name: str) -> str:
    safe = name.replace("/", "").replace("\\", "").replace(".", "")
    path = _STYLES_DIR / f"{safe}.yaml"
    if not path.exists():
        raise KeyError(f"unknown style: {name}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["text"]


def render_notes_system(mode: str, vars: dict[str, Any]) -> str:
    template = _env.get_template(f"{mode}.j2")
    return template.render(**vars)


def available_styles() -> list[str]:
    return sorted(p.stem for p in _STYLES_DIR.glob("*.yaml"))
