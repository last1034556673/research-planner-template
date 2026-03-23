"""Bundled CSS and HTML template assets for rendered outputs."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent


def load_css(name: str) -> str:
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")
