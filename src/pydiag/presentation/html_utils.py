from __future__ import annotations

from html import escape as html_escape


def safe_text(value: object) -> str:
    return html_escape(str(value))
