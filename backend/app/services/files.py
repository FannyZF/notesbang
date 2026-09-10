"""Local upload/export file helpers (object storage arrives in a later phase).

The upload root mirrors the private helper previously used by the project
routes so exporters can resolve the original file for PPTX write-back.
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def upload_root() -> Path:
    settings = get_settings()
    base = Path("tests_tmp" if settings.environment == "test" else "storage")
    return base / "uploads"


def upload_path(source_key: str) -> Path:
    return upload_root() / source_key


def export_dir() -> Path:
    settings = get_settings()
    base = Path("tests_tmp" if settings.environment == "test" else "storage")
    return base / "exports"
