"""PDF rendering.

WeasyPrint turns the report's HTML into a print-quality PDF with real
typography, page breaks and running headers. It depends on system libraries
(Pango and Cairo); when those are missing the caller falls back to the browser's
own print dialogue, which produces an acceptable PDF from the same stylesheet.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def is_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        # OSError is what WeasyPrint raises when Pango or Cairo is absent.
        return False
    return True


def unavailable_reason() -> str | None:
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        return (
            "WeasyPrint is not installed. Run: pip install weasyprint"
        )
    except OSError as exc:
        return (
            "WeasyPrint is installed but its system libraries are missing "
            f"({exc}). On Debian/Ubuntu: sudo apt install libpango-1.0-0 "
            "libpangoft2-1.0-0 libcairo2. On macOS: brew install pango."
        )
    return None


def render(html: str, base_url: str | None = None) -> bytes:
    """Render a complete HTML document to PDF bytes."""
    from weasyprint import HTML

    return HTML(string=html, base_url=base_url).write_pdf()
