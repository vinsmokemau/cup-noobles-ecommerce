"""The sending half of the email outbox (SPEC.md §4.8, T11.1).

`send_pending()` renders and sends every pending `email_outbox` row whose backoff has elapsed. A
failed attempt increments `attempts` and keeps the row pending; the 6th failure leaves it for good
and raises an alert. "Failed" needs no column: it is an unsent row with `attempts >= MAX_ATTEMPTS`.

G17 is open: rows are not claimed, so two overlapping runs can send one row twice. P11-V10 is
written against the proposed resolution (`SELECT … FOR UPDATE SKIP LOCKED`) and is `xfail` until
the owner decides.
"""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.core import providers
from apps.notifications.email.base import OutgoingEmail
from apps.notifications.models import EmailOutbox
from apps.notifications.rendering import render_email

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
BACKOFF_BASE = timedelta(seconds=30)
_ERROR_MAX_LENGTH = 500


def next_attempt_at(row: EmailOutbox) -> datetime:
    """When the next attempt is due: at once, then 30 s, 90 s, 210 s, 450 s and 930 s after the row
    was queued (the wait doubles each time)."""
    return row.created_at + BACKOFF_BASE * (2**row.attempts - 1)


def send_pending(*, now: datetime | None = None) -> tuple[int, int]:
    """Attempt every due pending row. Returns (sent, failed attempts)."""
    now = now or timezone.now()
    pending = EmailOutbox.objects.filter(
        sent_at__isnull=True, attempts__lt=MAX_ATTEMPTS
    ).order_by("created_at", "pk")
    sent = failed = 0
    for row in pending.select_related("order"):
        if now < next_attempt_at(row):
            continue
        if _send_row(row):
            sent += 1
        else:
            failed += 1
    return sent, failed


def _send_row(row: EmailOutbox) -> bool:
    try:
        rendered = render_email(row.template, row.context, row.order)
        providers.email_sender().send(
            OutgoingEmail(
                to=row.to_email,
                subject=rendered.subject,
                html=rendered.html,
                text=rendered.text,
                template=row.template,
                reply_to=settings.EMAIL_REPLY_TO,
                outbox_id=row.pk,
            )
        )
    except Exception as exc:  # noqa: BLE001 - any failure leaves the row for the next attempt
        _record_failure(row, exc)
        return False
    EmailOutbox.objects.filter(pk=row.pk).update(sent_at=timezone.now())
    return True


def _record_failure(row: EmailOutbox, exc: Exception) -> None:
    row.attempts += 1
    row.last_error = f"{type(exc).__name__}: {exc}"[:_ERROR_MAX_LENGTH]
    EmailOutbox.objects.filter(pk=row.pk).update(
        attempts=row.attempts, last_error=row.last_error
    )
    if row.attempts >= MAX_ATTEMPTS:
        message = (
            f"email_outbox {row.pk} ({row.template}) failed {row.attempts} attempts "
            f"and will not be retried: {row.last_error}"
        )
        logger.error("ALERT %s", message)
        providers.error_reporter().capture_message(message, level="error")
    else:
        logger.warning(
            "email_outbox %s failed attempt %s: %s",
            row.pk,
            row.attempts,
            row.last_error,
        )
