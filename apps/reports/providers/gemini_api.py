"""Gemini narration, via Google AI Studio.

Accepts both key formats AI Studio issues: the legacy `AIza...` and the newer
`AQ....` authorization key. Both are passed through the SDK, which sends them
on the `x-goog-api-key` header the native Gemini endpoint expects.
"""

from __future__ import annotations

import json
import os

from .base import RESPONSE_SCHEMA, SYSTEM_PROMPT, user_prompt

NAME = "gemini"
DEFAULT_MODEL = "gemini-2.5-flash"
KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def api_key() -> str:
    for var in KEY_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return ""


def model() -> str:
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def sdk_version() -> str | None:
    try:
        import google.genai as genai
    except ImportError:
        return None
    return getattr(genai, "__version__", "unknown")


def key_looks_valid(key: str) -> bool:
    # AI Studio issues "AIza..." (legacy) and "AQ...." (current). Code that
    # hardcodes the AIza prefix is why some tools reject a perfectly good key.
    return key.startswith(("AIza", "AQ."))


def status() -> dict:
    key = api_key()
    version = sdk_version()
    return {
        "name": NAME,
        "label": "Google Gemini (AI Studio)",
        "sdk_package": "google-genai",
        "sdk_installed": version is not None,
        "sdk_version": version,
        "key_vars": KEY_VARS,
        "key_present": bool(key),
        "key_hint": f"{key[:6]}...{key[-4:]}" if len(key) > 12 else None,
        "key_looks_valid": key_looks_valid(key) if key else False,
        "model": model(),
        "console_url": "https://aistudio.google.com/apikey",
        "ready": version is not None and bool(key),
    }


def narrate(payload: dict, language: str) -> dict:
    """Returns the parsed JSON payload. Raises on any failure."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key())
    response = client.models.generate_content(
        model=model(),
        contents=user_prompt(json.dumps(payload, ensure_ascii=False), language),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=RESPONSE_SCHEMA,
            max_output_tokens=16000,
            # No tools are declared, so the SDK's automatic function calling
            # has nothing to do but does emit a warning on every call.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )

    text = response.text
    if not text:
        # Usually a safety block or an exhausted output budget; both surface
        # here as an empty body rather than an exception.
        raise RuntimeError(
            f"empty response (finish_reason="
            f"{getattr(response.candidates[0], 'finish_reason', 'unknown') if response.candidates else 'no candidates'})"
        )
    return json.loads(text)
