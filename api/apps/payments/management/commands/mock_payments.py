"""Dev tooling for the mock payment provider (SPEC.md 9.11, 9.12a). Refuses to run in production."""

import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.payments.devtools import delivery

POLL_SECONDS = 0.5


class Command(BaseCommand):
    help = "Drive the mock payment provider (SPEC.md 9.11)."

    def add_arguments(self, parser: CommandParser) -> None:
        actions = parser.add_subparsers(dest="action", required=True)
        deliver = actions.add_parser(
            "deliver", help="Send the queued notifications to the webhook."
        )
        mode = deliver.add_mutually_exclusive_group()
        mode.add_argument(
            "--once",
            action="store_true",
            help="Send everything queued now, ignoring the delay, then exit (the default).",
        )
        mode.add_argument(
            "--loop",
            action="store_true",
            help="Keep sending, each notification after MOCK_WEBHOOK_DELAY_SECONDS.",
        )
        deliver.add_argument(
            "--base-url",
            default=None,
            help="Where to POST; defaults to SITE_URL. In compose: http://proxy:8080.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ENABLED:
            raise CommandError("mock_payments runs only where DEV_TOOLS_ENABLED is on")
        if options["action"] == "deliver":
            self._deliver(
                options["base_url"] or str(settings.SITE_URL), options["loop"]
            )

    def _deliver(self, base_url: str, loop: bool) -> None:
        transport = delivery.http_transport(base_url)
        if not loop:
            result = delivery.deliver(transport, honour_delay=False)
            self._report(result)
            return
        self.stdout.write(
            f"mock_payments deliver: watching the queue, posting to {base_url}"
        )
        while True:
            result = delivery.deliver(transport, honour_delay=True)
            if result.delivered or result.failed:
                self._report(result)
            time.sleep(POLL_SECONDS)

    def _report(self, result: delivery.DeliveryResult) -> None:
        self.stdout.write(
            f"mock_payments deliver: {result.delivered} delivered, "
            f"{result.failed} failed, {result.waiting} waiting"
        )
