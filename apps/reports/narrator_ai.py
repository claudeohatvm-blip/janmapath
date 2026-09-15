"""Optional AI narration.

The engine's findings and every conclusion in the report are produced without
any model. This module only rewrites the prose - for fluency, and for languages
other than English.

Two providers are supported: Google Gemini (AI Studio) and Anthropic Claude.
Whichever has a key configured is used; set AI_PROVIDER to pin one. If neither
is available - no key, no SDK, an API error - the caller silently keeps the
rule-written text, so a report is never blocked on a model.
"""

from __future__ import annotations

import logging
import os

from .providers import anthropic_api, gemini_api
from .providers.base import LANGUAGES
from .schema import Report, Section

logger = logging.getLogger(__name__)

__all__ = ["LANGUAGES", "is_configured", "narrate", "status", "active_provider"]

# Gemini first: AI Studio issues a key without a card, which makes it the
# usual starting point. Order only matters when both are configured.
PROVIDERS = (gemini_api, anthropic_api)
_BY_NAME = {p.NAME: p for p in PROVIDERS}


def active_provider():
    """The provider that will actually be used, or None.

    AI_PROVIDER pins a choice: "gemini", "anthropic", or "none" to disable AI
    narration entirely even when a key is present. Anything else, including
    unset, means auto-detect.
    """
    choice = os.environ.get("AI_PROVIDER", "auto").strip().lower()

    if choice == "none":
        return None
    if choice in _BY_NAME:
        provider = _BY_NAME[choice]
        return provider if provider.status()["ready"] else None

    return next((p for p in PROVIDERS if p.status()["ready"]), None)


def is_configured() -> bool:
    """Whether AI narration can run right now."""
    return active_provider() is not None


def status() -> dict:
    """Diagnostic detail for the setup page.

    The top-level keys describe the provider that would actually run, so a
    template can read them without knowing which one it is.
    """
    provider = active_provider()
    pinned = os.environ.get("AI_PROVIDER", "auto").strip().lower()
    all_status = [p.status() for p in PROVIDERS]

    active = next((s for s in all_status if provider and s["name"] == provider.NAME), None)

    return {
        "ready": active is not None,
        "provider": active["name"] if active else None,
        "provider_label": active["label"] if active else None,
        "model": active["model"] if active else None,
        "sdk_installed": active["sdk_installed"] if active else False,
        "sdk_version": active["sdk_version"] if active else None,
        "key_present": active["key_present"] if active else False,
        "key_hint": active["key_hint"] if active else None,
        "key_looks_valid": active["key_looks_valid"] if active else False,
        "pinned": pinned if pinned in {*_BY_NAME, "none"} else None,
        "providers": all_status,
    }


def narrate(report: Report, findings: dict, language: str = "en") -> Report:
    """Rewrite the report's prose. Returns the original unchanged on any failure."""
    provider = active_provider()
    if provider is None:
        return report

    payload = {
        "language": LANGUAGES.get(language, "English"),
        "findings": findings,
        "draft": [
            {
                "key": s.key,
                "title": s.title,
                "summary": s.summary,
                "paragraphs": s.paragraphs,
                "key_points": s.key_points,
            }
            for s in report.sections
        ],
    }

    try:
        result = provider.narrate(payload, language)
        rewritten = {s["key"]: s for s in result["sections"]}
    except Exception as exc:                        # noqa: BLE001 - never block the report
        logger.warning(
            "AI narration unavailable via %s (%s); keeping rule-written text",
            provider.NAME,
            exc,
        )
        return report

    merged: list[Section] = []
    for section in report.sections:
        new = rewritten.get(section.key)
        if not new:
            merged.append(section)
            continue
        # Scores, bands and evidence come from the engine and are never touched.
        merged.append(
            Section(
                key=section.key,
                title=section.title,
                summary=new.get("summary") or section.summary,
                band=section.band,
                score=section.score,
                paragraphs=new.get("paragraphs") or section.paragraphs,
                key_points=new.get("key_points") or section.key_points,
                evidence=section.evidence,
                is_free=section.is_free,
            )
        )

    report.sections = merged
    report.narrator = f"{provider.NAME}:{provider.model()}"
    return report
