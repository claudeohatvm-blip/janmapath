#!/usr/bin/env python
import os
import sys
from pathlib import Path

# The engine and report layer live at the repo root, outside this package.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_dotenv() -> None:
    """Minimal .env loader so the documented setup works with no extra package.

    Existing environment variables always win, so an exported key is never
    overridden by a stale file.
    """
    for candidate in (Path(__file__).resolve().parent / ".env", ROOT / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> None:
    load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
