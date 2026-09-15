"""Claude narration, via the Anthropic API."""

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

NAME = "anthropic"
DEFAULT_MODEL = "claude-opus-5"
KEY_VARS = ("ANTHROPIC_API_KEY",)


def api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)


def sdk_version() -> str | None:
    try:
        import anthropic
    except ImportError:
        return None
    return getattr(anthropic, "__version__", "unknown")


def status() -> dict:
    key = api_key()
    version = sdk_version()
    return {
        "name": NAME,
        "label": "Anthropic Claude",
        "sdk_package": "anthropic",
        "install_command": install_command("anthropic"),
        "python_executable": python_executable(),
        "in_virtualenv": in_virtualenv(),
        "sdk_installed": version is not None,
        "sdk_version": version,
        "key_vars": KEY_VARS,
        "key_present": bool(key),
        "key_hint": f"{key[:7]}...{key[-4:]}" if len(key) > 14 else None,
        "key_looks_valid": key.startswith("sk-ant-") if key else False,
        "model": model(),
        "console_url": "https://console.anthropic.com",
        "ready": version is not None and bool(key),
    }


def narrate(payload: dict, language: str) -> dict:
    """Returns the parsed JSON payload. Raises on any failure."""
    import anthropic

    client = anthropic.Anthropic()
    with client.messages.stream(
        model=model(),
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": user_prompt(json.dumps(payload, ensure_ascii=False), language),
            }
        ],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise RuntimeError("request declined by safety classifier")

    return json.loads(next(b.text for b in response.content if b.type == "text"))
