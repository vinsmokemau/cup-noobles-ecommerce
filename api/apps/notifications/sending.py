"""The sending half of the email outbox (SPEC.md §4.8, T11.1).

`send_pending()` renders and sends every pending `email_outbox` row whose backoff has elapsed. A
failed attempt increments `attempts` and keeps the row pending; the 6th failure leaves it for good
and raises an alert. "Failed" needs no column: it is an unsent row with `attempts >= MAX_ATTEMPTS`.

Each attempt locks its row with `SELECT … FOR UPDATE SKIP LOCKED` and skips one another run holds,
so two overlapping runs send a row once (G17, ADR-0053).
"""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core import providers
from apps.invoicing.models import InvoiceDocument
from apps.notifications.email.base import Attachment, OutgoingEmail
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
        outcome = _attempt(row.pk, now)
        if outcome is True:
            sent += 1
        elif outcome is False:
            failed += 1
    return sent, failed


def _attempt(pk: int, now: datetime) -> bool | None:
    """One attempt at a row, holding its lock. None when another run holds it or it is no longer due."""
    with transaction.atomic():
        row = (
            EmailOutbox.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("order")
            .filter(pk=pk, sent_at__isnull=True, attempts__lt=MAX_ATTEMPTS)
            .first()
        )
        if row is None or now < next_attempt_at(row):
            return None
        return _send_row(row)


_CONTENT_TYPES = {
    InvoiceDocument.Kind.PDF: "application/pdf",
    InvoiceDocument.Kind.XML: "application/xml",
}


def _attachments(row: EmailOutbox) -> tuple[Attachment, ...]:
    """The CFDI files of the invoice request named in the row's context, read now and never copied
    into the outbox (REQ-060). A row without `invoice_request_id` has none; a request missing its
    PDF or XML raises, so the row stays pending."""
    request_id = row.context.get("invoice_request_id")
    if request_id is None:
        return ()
    documents = {
        d.kind: d for d in InvoiceDocument.objects.filter(invoice_request_id=request_id)
    }
    missing = {k.value for k in _CONTENT_TYPES} - documents.keys()
    if missing:
        raise ValueError(
            f"Invoice request {request_id} has no {', '.join(sorted(missing))} document"
        )
    return tuple(
        Attachment(
            filename=documents[kind].filename,
            content_type=content_type,
            content=bytes(documents[kind].content),
        )
        for kind, content_type in _CONTENT_TYPES.items()
    )


def _send_row(row: EmailOutbox) -> bool:
    try:
        rendered = render_email(row.template, row.context, row.order)
        attachments = _attachments(row)
        providers.email_sender().send(
            OutgoingEmail(
                to=row.to_email,
                subject=rendered.subject,
                html=rendered.html,
                text=rendered.text,
                template=row.template,
                reply_to=settings.EMAIL_REPLY_TO,
                attachments=attachments,
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
