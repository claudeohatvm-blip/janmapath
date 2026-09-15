"""Run the demo so other devices on the same network can reach it.

`runserver` binds to 127.0.0.1 by default, which only the host machine can
reach. This binds to every interface and prints the address to type on a phone
or another laptop, so showing the demo to someone does not start with a round of
"what's your IP".
"""

from __future__ import annotations

import os
import socket

from django.core.management import call_command
from django.core.management.base import BaseCommand


def lan_address() -> str | None:
    """This machine's address on the local network.

    Opens a UDP socket toward a public address and reads back which local
    interface the routing table chose. No packet is ever sent, so this works
    offline and needs no permissions.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


class Command(BaseCommand):
    help = "Run the demo on all interfaces and print the address for other devices."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--port", type=int, default=8000)

    def handle(self, *args, **options) -> None:
        port = options["port"]

        # The autoreloader re-executes this command in a child process, so
        # printing unconditionally shows the banner twice. Only the parent
        # prints it.
        if os.environ.get("RUN_MAIN") == "true":
            call_command("runserver", f"0.0.0.0:{port}")
            return

        address = lan_address()

        bold = self.style.MIGRATE_HEADING
        ok = self.style.SUCCESS

        self.stdout.write("")
        self.stdout.write(bold("  JanmaPath demo"))
        self.stdout.write("")
        self.stdout.write(f"  On this machine   http://127.0.0.1:{port}")
        if address:
            self.stdout.write(f"  On this network   {ok(f'http://{address}:{port}')}")
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "  Open that second address on any phone or laptop joined to\n"
                    "  the same Wi-Fi. If it does not load, the host firewall is\n"
                    f"  almost certainly blocking port {port} - see demo/README.md."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  Could not determine this machine's network address.\n"
                    "  Find it with `ip addr` (Linux), `ipconfig getifaddr en0`\n"
                    "  (macOS) or `ipconfig` (Windows)."
                )
            )
        self.stdout.write("")

        # use_reloader is left on: this is still the development server.
        call_command("runserver", f"0.0.0.0:{port}")
