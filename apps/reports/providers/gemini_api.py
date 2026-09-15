"""Gemini narration, via Google AI Studio.

Accepts both key formats AI Studio issues: the legacy `AIza...` and the newer
`AQ....` authorization key. Both are passed through the SDK, which sends them
on the `x-goog-api-key` header the native Gemini endpoint expects.
"""

from __future__ import annotations

import json
import os

from .base import (
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    in_virtualenv,
    install_command,
    python_executable,
    user_prompt,
)

NAME = "gemini"
# Google retires model IDs, and a hardcoded default in a distributed app goes
# stale silently - the request 404s with "no longer available to new users".
# list_models() on the setup page is the durable fix: it shows what this key can
# actually reach today, so a stale default is visible rather than mysterious.
DEFAULT_MODEL = "gemini-3.6-flash"
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
        "install_command": install_command("google-genai"),
        "python_executable": python_executable(),
        "in_virtualenv": in_virtualenv(),
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


def _suggested_model(message: str) -> str | None:
    """Pull the replacement model Google names in a retirement 404."""
    import re

    match = re.search(r"use\s+models/([A-Za-z0-9._-]+)", message)
    return match.group(1) if match else None


def list_models() -> list[dict]:
    """Models this key can actually use for generateContent.

    Returns [] on any failure - this is a diagnostic aid, never a hard
    dependency.
    """
    try:
        from google import genai

        client = genai.Client(api_key=api_key())
        found = []
        for m in client.models.list():
            actions = m.supported_actions or []
            if actions and "generateContent" not in actions:
                continue
            name = (m.name or "").removeprefix("models/")
            if not name:
                continue
            found.append(
                {
                    "id": name,
                    "label": m.display_name or name,
                    "output_limit": m.output_token_limit,
                }
            )
        return sorted(found, key=lambda x: x["id"], reverse=True)
    except Exception:                               # noqa: BLE001 - diagnostic only
        return []


_RETIRED_HINT = "no longer available"


def narrate(payload: dict, language: str) -> dict:
    """Returns the parsed JSON payload. Raises on any failure."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key())
    try:
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
    except Exception as exc:                        # noqa: BLE001 - re-raised below
        message = str(exc)
        if _RETIRED_HINT in message:
            # Google names the replacement in the 404 body; surface it rather
            # than leaving the operator to read a wall of JSON.
            suggested = _suggested_model(message)
            raise RuntimeError(
                f"model {model()!r} has been retired"
                + (f"; set GEMINI_MODEL={suggested}" if suggested else "")
                + ". Open /setup/ai to see the models this key can use."
            ) from exc
        raise

    text = response.text
    if not text:
        # Usually a safety block or an exhausted output budget; both surface
        # here as an empty body rather than an exception.
        raise RuntimeError(
            f"empty response (finish_reason="
            f"{getattr(response.candidates[0], 'finish_reason', 'unknown') if response.candidates else 'no candidates'})"
        )
    return json.loads(text)
