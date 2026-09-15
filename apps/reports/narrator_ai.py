"""Optional AI narration.

The engine's findings and every conclusion in the report are produced without
any model. This module only rewrites the prose - for fluency, and for languages
other than English.

It is given the structured findings and the rule-written draft, and is
constrained to narrate only what it receives. It may not calculate, infer a
placement, or introduce a claim that is not already in the findings. If it is
unavailable - no API key, no SDK, an API error - the caller silently keeps the
rule-written text, so the report is never blocked on it.
"""

from __future__ import annotations

import json
import logging
import os

from .schema import Report, Section

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 16000

LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
    "mr": "Marathi",
}

SYSTEM_PROMPT = """\
You are the writer for JanmaPath, a Vedic astrology service. You receive \
astrological findings that have already been computed, together with a plain \
draft written from those findings.

Your only task is to rewrite the draft so it reads well.

Absolute constraints:
- Narrate ONLY what appears in the findings. Never calculate, infer, or \
introduce a placement, dosha, yoga, house, sign, or prediction that is not \
already present in the input.
- Never change a conclusion, a score, a band, or a verdict. If the draft says \
an area is challenged, your version says so too.
- If a field is absent from the findings, do not mention that topic at all. \
Absent house data means the birth time was not known; never supply an \
ascendant, house placement, or anything derived from them.
- Keep every specific detail: sign names, house numbers, graha names, degrees, \
nakshatras. These are the substance of the reading.
- Write with warmth and directness. Address the reader as "you". No hedging \
filler, no horoscope-column cliches, no invented drama.
- Never promise outcomes. Vedic readings describe tendency and timing, not \
certainty. Avoid medical, legal and financial directives.

Return each section's paragraphs rewritten, in the same order, with the same \
count. Preserve any leading four-space indentation, which marks a remedy line.\
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "summary": {"type": "string"},
                    "paragraphs": {"type": "array", "items": {"type": "string"}},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["key", "summary", "paragraphs", "key_points"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sections"],
    "additionalProperties": False,
}


def is_configured() -> bool:
    """Whether AI narration can run right now."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def status() -> dict:
    """Diagnostic detail for the setup page."""
    try:
        import anthropic

        sdk_version = getattr(anthropic, "__version__", "unknown")
        sdk_installed = True
    except ImportError:
        sdk_version = None
        sdk_installed = False

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return {
        "sdk_installed": sdk_installed,
        "sdk_version": sdk_version,
        "key_present": bool(key),
        "key_hint": f"{key[:7]}...{key[-4:]}" if len(key) > 14 else None,
        "key_looks_valid": key.startswith("sk-ant-"),
        "model": MODEL,
        "ready": sdk_installed and bool(key),
    }


def narrate(report: Report, findings: dict, language: str = "en") -> Report:
    """Rewrite the report's prose. Returns the original unchanged on any failure."""
    if not is_configured():
        return report

    import anthropic

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
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Rewrite this reading in {LANGUAGES.get(language, 'English')}.\n\n"
                        + json.dumps(payload, ensure_ascii=False)
                    ),
                }
            ],
        ) as stream:
            response = stream.get_final_message()

        if response.stop_reason == "refusal":
            logger.warning("AI narration refused; keeping rule-written text")
            return report

        text = next(b.text for b in response.content if b.type == "text")
        rewritten = {s["key"]: s for s in json.loads(text)["sections"]}

    except Exception as exc:                        # noqa: BLE001 - never block the report
        logger.warning("AI narration unavailable (%s); keeping rule-written text", exc)
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
    report.narrator = MODEL
    return report
