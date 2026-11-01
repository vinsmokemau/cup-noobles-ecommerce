"""Send queued email (SPEC.md §4.8, T11.1)."""

from typing import Any

from django.core.management.base import BaseCommand

from apps.notifications.sending import send_pending


class Command(BaseCommand):
    help = "Render and send pending email_outbox rows (SPEC.md §4.8)."

    def handle(self, *args: Any, **options: Any) -> None:
        sent, failed = send_pending()
        self.stdout.write(f"send_outbox: {sent} sent, {failed} failed")
