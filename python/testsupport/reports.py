"""Report helpers for tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def pdf_text(data: bytes, tmp_path: Path) -> str | None:
    """The PDF's text, when poppler's pdftotext is installed."""
    binary = shutil.which("pdftotext")
    if binary is None:
        return None
    path = tmp_path / "report.pdf"
    path.write_bytes(data)
    text = subprocess.run(  # noqa: S603 - a fixed binary on a file the test wrote
        [binary, str(path), "-"], check=True, capture_output=True, text=True
    ).stdout
    return " ".join(text.split())
