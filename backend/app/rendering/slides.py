"""Slide rendering: PPTX -> PDF (LibreOffice) -> per-page PNG (PyMuPDF).

Both tools are optional. If LibreOffice is unavailable the renderer returns an
empty list so uploads keep working (thumbnails/vision simply disabled).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.config import get_settings

_COMMON_SOFFICE = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
]


def find_soffice() -> str | None:
    settings = get_settings()
    if settings.soffice_path and Path(settings.soffice_path).exists():
        return settings.soffice_path
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    for candidate in _COMMON_SOFFICE:
        if Path(candidate).exists():
            return candidate
    return None


def render_pages(source_path: str | Path, dpi: int = 110) -> list[bytes]:
    """Return PNG bytes per slide, or [] when rendering is unavailable."""
    soffice = find_soffice()
    if soffice is None:
        return []
    try:
        import pymupdf  # noqa: F401
    except Exception:  # noqa: BLE001
        return []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp_path),
                    str(source_path),
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
        except Exception:  # noqa: BLE001 - conversion failed
            return []
        pdfs = list(tmp_path.glob("*.pdf"))
        if not pdfs:
            return []
        import pymupdf

        images: list[bytes] = []
        with pymupdf.open(pdfs[0]) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                images.append(pix.tobytes("png"))
        return images
