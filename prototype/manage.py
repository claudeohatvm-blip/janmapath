#!/usr/bin/env python
import os
import sys
from pathlib import Path

# The pure engine lives at the repo root, outside this prototype package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
