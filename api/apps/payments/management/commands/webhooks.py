"""Dev tooling: re-send stored payment notifications (SPEC.md 9.12b). Refuses to run in production."""

from collections import Counter
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.payments.devtools import delivery, replay


class Command(BaseCommand):
    help = "Replay, duplicate, tamper with or backdate a stored notification (SPEC.md 9.12b)."

    def add_arguments(self, parser: CommandParser) -> None:
        actions = parser.add_subparsers(dest="action", required=True)
        for name, help_text in (
            (
                "replay",
                "Re-send it with the same notification id, freshly signed. A no-op.",
            ),
            ("tamper", "Re-send it with a corrupted signature. Expect 401."),
            (
                "stale",
                "Re-send it signed older than WEBHOOK_MAX_AGE_SECONDS. Expect 401.",
            ),
        ):
            actions.add_parser(name, help=help_text)
        duplicate = actions.add_parser(
            "duplicate", help="Deliver it N times. Exactly one delivery is processed."
        )
        duplicate.add_argument("--count", type=int, required=True)
        duplicate.add_argument("--concurrent", action="store_true")
        for sub in actions.choices.values():
            sub.add_argument("event", type=int, help="webhook_event id")
            sub.add_argument(
                "--base-url",
                default=None,
                help="Where to POST; defaults to SITE_URL. In compose: http://proxy:8080.",
            )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEV_TOOLS_ENABLED:
            raise CommandError("webhooks runs only where DEV_TOOLS_ENABLED is on")
        action = options["action"]
        event = replay.verified_event(options["event"])
        base_url = options["base_url"] or str(settings.SITE_URL)

        def transport() -> delivery.Transport:
            return delivery.http_transport(
                base_url, delivery.webhook_path(event.provider)
            )

        if action == "duplicate":
            if options["count"] < 1:
                raise CommandError("--count must be at least 1")
            statuses = replay.send_many(
                transport, event, options["count"], concurrent=options["concurrent"]
            )
            summary = ", ".join(
                f"{n} x {s}" for s, n in sorted(Counter(statuses).items())
            )
            self.stdout.write(
                f"webhooks duplicate: {len(statuses)} deliveries -> {summary}"
            )
            if any(status != 200 for status in statuses):
                raise CommandError("Every duplicate delivery should answer 200")
            return

        if action == "replay":
            body, headers = replay.build_request(event)
            expected = 200
        elif action == "tamper":
            body, headers = replay.build_request(event, corrupt=True)
            expected = 401
        else:
            body, headers = replay.build_request(event, ts=replay.stale_ts())
            expected = 401
        status = transport()(body, headers)
        self.stdout.write(f"webhooks {action}: {status} (expected {expected})")
        if status != expected:
            raise CommandError(f"webhooks {action} expected {expected}, got {status}")
