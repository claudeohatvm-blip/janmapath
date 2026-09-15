"""Shared contract for AI narration providers.

Every provider receives the same prompt, the same JSON schema, and the same
hard constraint: rewrite the wording, never the findings. A provider returns
the parsed JSON payload, or raises - the caller turns any failure into "keep
the rule-written text".
"""

from __future__ import annotations

import shlex
import sys


def python_executable() -> str:
    """The interpreter actually running this server."""
    return sys.executable


def in_virtualenv() -> bool:
    return sys.prefix != sys.base_prefix


def install_command(package: str) -> str:
    """A pip command guaranteed to target the running interpreter.

    A bare `pip install` resolves through PATH, which on most machines is the
    system Python rather than the project's virtualenv - and a virtualenv
    ignores ~/.local/lib by default, so a user-site install stays invisible to
    it. Running pip as a module of a named interpreter removes the ambiguity.
    """
    return f"{shlex.quote(sys.executable)} -m pip install {package}"

LANGUAGES: dict[str, str] = {
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

# Kept to the intersection both providers accept: no $ref, no anyOf, every
# object closed with additionalProperties false and an explicit required list.
RESPONSE_SCHEMA: dict = {
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


def user_prompt(payload_json: str, language: str) -> str:
    return (
        f"Rewrite this reading in {LANGUAGES.get(language, 'English')}.\n\n"
        + payload_json
    )
