"""Receiving and processing payment notifications (SPEC.md 9.A, 9.B, T9.3).

The endpoint verifies, inserts the `webhook_event` row, tries to process it inline and answers 200
either way. A row that fails stays unprocessed and `process_webhooks` retries it, up to
`MAX_ATTEMPTS` attempts with exponential backoff, then leaves it failed and alerts (G7, ADR-0044).

"Failed" needs no column: it is an unprocessed, verified row with `attempts >= MAX_ATTEMPTS`.
`attempts` counts every processing attempt, the inline one included.
"""

import json
import logging
import time
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.providers import payment_provider
from apps.orders.models import Order
from apps.payments.base import ProviderPayment
from apps.payments.mapping import PAYMENT_STATUS, apply_payment_status
from apps.payments.models import Payment, WebhookEvent

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 10
BACKOFF_BASE = timedelta(seconds=30)
_ERROR_MAX_LENGTH = 2000


class InlineBudgetExceeded(Exception):
    """The provider took longer than `WEBHOOK_INLINE_BUDGET_MS`; `process_webhooks` takes over."""


def receive_notification(
    provider_code: str, headers: Mapping[str, str], body: bytes
) -> HTTPStatus:
    """Steps 1 to 4 of the endpoint. The caller has already matched `provider_code`."""
    provider = payment_provider()
    parsed = _parse(body)
    ref = provider.verify_webhook(headers, body)
    if ref is None:
        try:
            _store_unverified(provider_code, headers, parsed)
        except Exception:  # noqa: BLE001 - a body the database refuses is still a 401
            logger.exception("Could not store a rejected payment notification")
        logger.warning("Payment notification rejected: signature check failed")
        return HTTPStatus.UNAUTHORIZED

    try:
        with transaction.atomic():
            event = WebhookEvent.objects.create(
                provider=provider_code,
                topic=ref.topic,
                external_id=ref.notification_id,
                signature_ok=True,
                payload={
                    "ref": {
                        "topic": ref.topic,
                        "notification_id": ref.notification_id,
                        "resource_id": ref.resource_id,
                    },
                    "body": parsed,
                },
                headers=dict(headers),
            )
    except IntegrityError:
        return HTTPStatus.OK  # a duplicate delivery of a notification already seen

    process_webhook_event(event.pk, budget_ms=settings.WEBHOOK_INLINE_BUDGET_MS)
    return HTTPStatus.OK


def process_webhook_event(event_id: int, *, budget_ms: int | None = None) -> bool:
    """One attempt at a row. True when the row is now processed; a failure is recorded, not raised.

    The row stays locked for the attempt, and a row another worker holds is skipped, so the inline
    attempt, the cron job and a second cron job never process one row twice.
    """
    started = time.monotonic()
    try:
        with transaction.atomic():
            event = (
                WebhookEvent.objects.select_for_update(skip_locked=True)
                .filter(
                    pk=event_id,
                    processed_at__isnull=True,
                    signature_ok=True,
                    attempts__lt=MAX_ATTEMPTS,
                )
                .first()
            )
            if event is None:
                return False
            event.attempts += 1
            event.error = _process(event, started=started, budget_ms=budget_ms)
            event.processed_at = timezone.now()
            event.save(update_fields=["attempts", "error", "processed_at"])
            return True
    except Exception as exc:  # noqa: BLE001 - any failure leaves the row for the next attempt
        _record_failure(event_id, exc)
        return False


def retry_due_events(*, now: datetime | None = None) -> tuple[int, int]:
    """Attempt every row whose backoff has elapsed. Returns (processed, still failing)."""
    now = now or timezone.now()
    candidates = WebhookEvent.objects.filter(
        processed_at__isnull=True, signature_ok=True, attempts__lt=MAX_ATTEMPTS
    ).order_by("received_at", "pk")
    processed = failing = 0
    for event in candidates:
        if now < next_attempt_at(event):
            continue
        if process_webhook_event(event.pk):
            processed += 1
        else:
            failing += 1
    return processed, failing


def next_attempt_at(event: WebhookEvent) -> datetime:
    """When the next attempt is due: 30 s after the first failure, then 90 s, 210 s, 450 s, ...
    after the row arrived (the wait doubles each time), up to about 4 h before the 10th."""
    return event.received_at + BACKOFF_BASE * (2**event.attempts - 1)


def _process(event: WebhookEvent, *, started: float, budget_ms: int | None) -> str:
    """The body of `process_webhook_event`; returns the row's `error` text ('' when clean)."""
    ref = event.payload["ref"]
    if ref["topic"] != "payment":
        return f"Ignored topic {ref['topic']!r}"

    provider = payment_provider()
    provider_payment = provider.fetch_payment(ref["resource_id"])
    if budget_ms is not None and (time.monotonic() - started) * 1000 > budget_ms:
        raise InlineBudgetExceeded(f"The provider took more than {budget_ms} ms")

    return process_provider_payment(event.provider, provider_payment)


def process_provider_payment(
    provider_code: str, provider_payment: ProviderPayment
) -> str:
    """Upsert the payment row, then apply the 9.4 mapping. Shared by webhooks and reconciliation
    (9.7). Returns an error text ('' when clean): a payment for an unknown order is alerted, not
    raised."""
    order = _order_for(provider_payment.external_reference)
    if order is None:
        message = (
            f"No order has public_id {provider_payment.external_reference!r} "
            f"(payment {provider_payment.provider_payment_id})"
        )
        logger.error("ALERT payment notification for an unknown order: %s", message)
        return message

    payment, _ = Payment.objects.update_or_create(
        provider=provider_code,
        provider_payment_id=provider_payment.provider_payment_id,
        defaults={
            "order": order,
            "status": PAYMENT_STATUS[provider_payment.status],
            "method": provider_payment.method,
            "amount_cents": provider_payment.amount_cents,
            "refunded_cents": provider_payment.refunded_cents,
            "installments": provider_payment.installments,
            "voucher_url": provider_payment.voucher_url,
            "voucher_expires_at": provider_payment.voucher_expires_at,
            "raw": dict(provider_payment.raw),
        },
    )
    apply_payment_status(order, payment, provider_payment)
    return ""


def _order_for(external_reference: str) -> Order | None:
    try:
        public_id = uuid.UUID(external_reference)
    except ValueError:
        return None
    return Order.objects.filter(public_id=public_id).first()


def _record_failure(event_id: int, exc: Exception) -> None:
    with transaction.atomic():
        event = (
            WebhookEvent.objects.select_for_update()
            .filter(pk=event_id, processed_at__isnull=True)
            .first()
        )
        if event is None:
            return
        event.attempts += 1
        event.error = f"{type(exc).__name__}: {exc}"[:_ERROR_MAX_LENGTH]
        event.save(update_fields=["attempts", "error"])
    if event.attempts >= MAX_ATTEMPTS:
        logger.error(
            "ALERT webhook_event %s failed %s attempts and will not be retried: %s",
            event.pk,
            event.attempts,
            event.error,
        )
    else:
        logger.warning(
            "webhook_event %s failed attempt %s: %s",
            event.pk,
            event.attempts,
            event.error,
        )


def _store_unverified(
    provider_code: str, headers: Mapping[str, str], parsed: Any
) -> None:
    topic = parsed.get("type") if isinstance(parsed, dict) else None
    WebhookEvent.objects.create(
        provider=provider_code,
        topic=topic if isinstance(topic, str) and topic else "unknown",
        external_id=f"unverified-{uuid.uuid4().hex}",
        signature_ok=False,
        payload={"body": parsed},
        headers=dict(headers),
        error="Signature verification failed",
    )


def _parse(body: bytes) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        return {"unparsed": body.decode("utf-8", errors="replace")}
