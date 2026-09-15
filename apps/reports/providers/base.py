"""Shared contract for AI narration providers.

Every provider receives the same prompt, the same JSON schema, and the same
hard constraint: rewrite the wording, never the findings. A provider returns
the parsed JSON payload, or raises - the caller turns any failure into "keep
the rule-written text".
"""

from __future__ import annotations

import logging
import random
import re
import shlex
import sys
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient on the provider's side - the same request will usually succeed a
# moment later. 429 is included because both providers use it for short-window
# rate limiting, not just hard quota exhaustion.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# A leading status code, as both SDKs format their error strings
# ("503 UNAVAILABLE. {...}"). Used only when no attribute carries the code.
_LEADING_STATUS = re.compile(r"^\s*(\d{3})\b")


def status_code(exc: BaseException) -> int | None:
    """The HTTP status behind an SDK exception, whichever name it uses."""
    for attribute in ("code", "status_code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    match = _LEADING_STATUS.match(str(exc))
    return int(match.group(1)) if match else None


def is_retryable(exc: BaseException) -> bool:
    """Whether retrying the identical request could plausibly succeed.

    Configuration errors - a bad key, a retired model, a malformed request -
    return 4xx and will fail identically forever, so retrying them only makes
    the user wait.
    """
    code = status_code(exc)
    if code is not None:
        return code in RETRYABLE_STATUS
    # No status at all usually means the request never completed: a dropped
    # connection or a read timeout. Both are worth one more try.
    return isinstance(exc, (TimeoutError, ConnectionError))


def with_retry(
    call: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    label: str = "request",
) -> T:
    """Run `call`, retrying transient failures with exponential backoff.

    Deliberately short: a person is watching a progress screen while this runs,
    so the ceiling is a few seconds, not a few minutes. Jitter keeps concurrent
    generations from retrying in lockstep.
    """
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:                    # noqa: BLE001 - re-raised below
            if attempt == attempts or not is_retryable(exc):
                raise
            delay = base_delay * (2 ** (attempt - 1)) * (0.75 + random.random() * 0.5)
            logger.warning(
                "%s failed with %s (attempt %d/%d); retrying in %.1fs",
                label,
                status_code(exc) or type(exc).__name__,
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)

    raise AssertionError("unreachable")             # pragma: no cover


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
