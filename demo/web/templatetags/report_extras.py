"""Template helpers for rendering report prose."""

from __future__ import annotations

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_BOLD = re.compile(r"\*\*(.+?)\*\*")


@register.filter
def prose(text: str) -> str:
    """Render a paragraph, honouring **bold** and the remedy indent.

    The narrators emit plain strings. Four leading spaces mark a remedy line,
    which renders as an indented bullet rather than a paragraph.
    """
    indented = text.startswith("    ")
    body = _BOLD.sub(r"<strong>\1</strong>", escape(text.strip()))
    # escape() turned the asterisks' neighbours safe; re-apply after escaping.
    body = _BOLD.sub(r"<strong>\1</strong>", body)
    css = "remedy" if indented else "para"
    return mark_safe(f'<p class="{css}">{body}</p>')


@register.filter
def band_class(band: str) -> str:
    return {
        "supported": "band-good",
        "mixed": "band-mixed",
        "challenged": "band-hard",
    }.get(band, "band-mixed")
