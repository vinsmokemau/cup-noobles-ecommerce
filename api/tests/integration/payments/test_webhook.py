"""Webhook processing: timestamps, unknown ids, retries (SPEC.md 9.A, T9.3, G7, G8, ADR-0044)."""

import logging
import time
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from apps.payments.base import PaymentNotFound
from apps.payments.mock import MockPaymentProvider
from apps.payments.models import Payment, WebhookEvent
from apps.payments.webhooks import MAX_ATTEMPTS, next_attempt_at
from tests.factories.orders import order_in_state
from tests.factories.payments import (
    mock_payment_for,
    post_notification,
    signed_notification,
)

START = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def pending_order(db):
    return order_in_state("pending_payment")


def alerts(caplog):
    return [r for r in caplog.records if "ALERT" in r.getMessage()]


def run_process_webhooks() -> str:
    out = StringIO()
    call_command("process_webhooks", stdout=out)
    return out.getvalue()


def test_p9_v10_timestamp_age_boundary(api_client, settings, clock, pending_order):
    clock.travel(START)
    now = int(START.timestamp())
    max_age = settings.WEBHOOK_MAX_AGE_SECONDS
    payment_id = mock_payment_for(pending_order)

    def deliver(ts):
        body, headers = signed_notification(settings, payment_id, ts=ts)
        return post_notification(api_client, body, headers).status_code

    assert deliver(now - max_age) == 200  # aged exactly the tolerance
    assert deliver(now - max_age - 1) == 401  # one second older
    assert deliver(now + max_age) == 200  # in the future by exactly the tolerance
    assert deliver(now + max_age + 1) == 401  # further in the future (G8)
    assert WebhookEvent.objects.filter(signature_ok=True).count() == 2
    assert WebhookEvent.objects.filter(signature_ok=False).count() == 2


def test_p9_v13_unknown_order_and_unknown_payment(
    api_client, settings, clock, pending_order, caplog
):
    clock.travel(START)
    caplog.set_level(logging.WARNING)

    # An unknown external_reference: processed with an error, and alerted (PAY-19).
    stranger = order_in_state("pending_payment")
    stranger_payment = mock_payment_for(stranger)
    stranger.delete()
    body, headers = signed_notification(settings, stranger_payment)
    assert post_notification(api_client, body, headers).status_code == 200
    event = WebhookEvent.objects.get()
    assert event.processed_at is not None
    assert "No order has public_id" in event.error
    assert len(alerts(caplog)) == 1
    assert Payment.objects.count() == 0

    # A resource id the provider does not know: retried like any failure (G7).
    body, headers = signed_notification(settings, "mock_pay_" + "f" * 32)
    assert post_notification(api_client, body, headers).status_code == 200
    ghost = WebhookEvent.objects.exclude(pk=event.pk).get()
    assert (ghost.processed_at, ghost.attempts) == (None, 1)
    assert "PaymentNotFound" in ghost.error
    caplog.clear()

    for attempt in range(2, MAX_ATTEMPTS + 1):
        clock.travel(next_attempt_at(ghost))
        run_process_webhooks()
        ghost.refresh_from_db()
        assert ghost.attempts == attempt
        assert ghost.processed_at is None
        assert bool(alerts(caplog)) is (attempt == MAX_ATTEMPTS)

    # Failed: not retried again, however long we wait.
    clock.travel(START + timedelta(days=30))
    run_process_webhooks()
    ghost.refresh_from_db()
    assert ghost.attempts == MAX_ATTEMPTS
    assert len(alerts(caplog)) == 1


def test_p9_v17_inline_failure_deferred(
    api_client, settings, clock, pending_order, monkeypatch
):
    clock.travel(START)
    payment_id = mock_payment_for(pending_order, status="approved")
    real_fetch = MockPaymentProvider.fetch_payment
    failures = [ConnectionError("provider timed out")]

    def flaky(self, provider_payment_id):
        if failures:
            raise failures.pop()
        return real_fetch(self, provider_payment_id)

    monkeypatch.setattr(MockPaymentProvider, "fetch_payment", flaky)
    body, headers = signed_notification(settings, payment_id)

    response = post_notification(api_client, body, headers)

    assert response.status_code == 200
    event = WebhookEvent.objects.get()
    assert (event.processed_at, event.attempts) == (None, 1)
    assert "ConnectionError" in event.error
    assert Payment.objects.count() == 0

    # The backoff has not elapsed: nothing to do yet.
    clock.travel(START + timedelta(seconds=29))
    assert "0 processed, 0 still failing" in run_process_webhooks()
    event.refresh_from_db()
    assert event.attempts == 1

    clock.travel(START + timedelta(seconds=30))
    assert "1 processed" in run_process_webhooks()
    event.refresh_from_db()
    assert event.processed_at is not None
    assert event.attempts == 2
    assert event.error == ""
    assert Payment.objects.get().provider_payment_id == payment_id

    # A processed row is never attempted again.
    run_process_webhooks()
    event.refresh_from_db()
    assert event.attempts == 2


def test_p9_v17_row_failed_after_ten_attempts(
    api_client, settings, clock, pending_order, monkeypatch, caplog
):
    clock.travel(START)
    caplog.set_level(logging.WARNING)

    def broken(self, provider_payment_id):
        raise PaymentNotFound(provider_payment_id)

    with monkeypatch.context() as patch:
        patch.setattr(MockPaymentProvider, "fetch_payment", broken)
        body, headers = signed_notification(settings, mock_payment_for(pending_order))
        post_notification(api_client, body, headers)
        event = WebhookEvent.objects.get()

        for _ in range(MAX_ATTEMPTS - 1):
            clock.travel(next_attempt_at(event))
            run_process_webhooks()
            event.refresh_from_db()

        assert (event.attempts, event.processed_at) == (MAX_ATTEMPTS, None)
        assert len(alerts(caplog)) == 1

    # Even once the provider recovers, a failed row is left alone.
    clock.travel(START + timedelta(days=30))
    assert "0 processed, 0 still failing" in run_process_webhooks()
    event.refresh_from_db()
    assert (event.attempts, event.processed_at) == (MAX_ATTEMPTS, None)


def test_backoff_doubles_between_attempts():
    waits = [
        (next_attempt_at(WebhookEvent(received_at=START, attempts=attempts)) - START)
        for attempts in range(1, MAX_ATTEMPTS)
    ]
    seconds = [wait.total_seconds() for wait in waits]

    assert seconds[:4] == [30, 90, 210, 450]
    gaps = [
        later - earlier for earlier, later in zip(seconds, seconds[1:], strict=False)
    ]
    assert gaps == [60 * 2**i for i in range(len(gaps))]


def test_slow_provider_is_left_for_the_cron_job(
    api_client, settings, pending_order, monkeypatch
):
    settings.WEBHOOK_INLINE_BUDGET_MS = 5
    real_fetch = MockPaymentProvider.fetch_payment

    def slow(self, provider_payment_id):
        time.sleep(0.05)
        return real_fetch(self, provider_payment_id)

    monkeypatch.setattr(MockPaymentProvider, "fetch_payment", slow)
    body, headers = signed_notification(settings, mock_payment_for(pending_order))

    assert post_notification(api_client, body, headers).status_code == 200

    event = WebhookEvent.objects.get()
    assert (event.processed_at, event.attempts) == (None, 1)
    assert "InlineBudgetExceeded" in event.error
    assert Payment.objects.count() == 0


def test_pending_then_approved_updates_one_payment(api_client, settings, pending_order):
    """9.A rule 4: two notifications for one payment are both processed and share one row."""
    payment_id = mock_payment_for(pending_order, status="pending", method="oxxo")
    first = signed_notification(settings, payment_id)
    assert post_notification(api_client, *first).status_code == 200
    assert Payment.objects.get().status == "pending"

    MockPaymentProvider().update_payment(payment_id, status="approved")
    second = signed_notification(settings, payment_id)
    assert post_notification(api_client, *second).status_code == 200

    assert WebhookEvent.objects.filter(processed_at__isnull=False).count() == 2
    assert Payment.objects.get().status == "approved"


def test_notification_of_another_topic_is_acknowledged_and_ignored(
    api_client, settings, db
):
    body, headers = signed_notification(
        settings, "merchant_order_1", topic="merchant_order"
    )

    assert post_notification(api_client, body, headers).status_code == 200

    event = WebhookEvent.objects.get()
    assert event.processed_at is not None
    assert "Ignored topic" in event.error
    assert Payment.objects.count() == 0
