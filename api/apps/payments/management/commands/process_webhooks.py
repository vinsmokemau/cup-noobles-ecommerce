"""Retry unprocessed webhook rows (SPEC.md §4.8, 9.A rule 5, T9.3).

A row that failed inline is attempted again once its backoff has elapsed. After 10 attempts it is
left failed (unprocessed, `attempts` at the cap), no longer retried, and an alert is logged
(G7, ADR-0044). Each attempt locks its row and skips one another worker holds, so two runs at once
process a row once.
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.payments.webhooks import retry_due_events


class Command(BaseCommand):
    help = "Retry unprocessed payment webhook rows (SPEC.md §4.8)."

    def handle(self, *args: Any, **options: Any) -> None:
        processed, failing = retry_due_events()
        self.stdout.write(
            f"process_webhooks: {processed} processed, {failing} still failing"
        )
