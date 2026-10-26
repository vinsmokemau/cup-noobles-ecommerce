"""Deadlines by payment method and the reservation guard (SPEC.md 9.5, ADR-0046, G48)."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from django.core.management import call_command

from apps.inventory import services
from apps.inventory.models import InventoryReservation
from apps.orders.models import Order
from apps.payments.mock import MockPaymentProvider
from tests.factories.inventory import stocked_variant
from tests.factories.orders import order_in_state
from tests.factories.payments import (
    mock_payment_for,
    post_notification,
    signed_notification,
)

CHECKOUT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
CARD_WINDOW = timedelta(minutes=30)
MICROSECOND = timedelta(microseconds=1)


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    cache.clear()
    yield
    cache.clear()


def checkout_at(clock, *, at=CHECKOUT):
    """A `pending_payment` order whose hold and deadline are the card window from `at`."""
    clock.travel(at)
    order = order_in_state("pending_payment", payment_deadline_at=at + CARD_WINDOW)
    services.reserve(order, [(stocked_variant(5), 1)], ttl=CARD_WINDOW)
    return order


def notify(api_client, settings, order, **payment):
    payment_id = mock_payment_for(order, **payment)
    body, headers = signed_notification(settings, payment_id)
    assert post_notification(api_client, body, headers).status_code == 200


def expires_at(order):
    return InventoryReservation.objects.get(order=order).expires_at


def release_due():
    call_command("expire_reservations")


def state_of(order):
    return Order.objects.get(pk=order.pk).state


def test_p9_v09_card_window_boundary(clock, api_client, settings, db):
    order = checkout_at(clock)
    # A card payment under review keeps the checkout window.
    clock.travel(CHECKOUT + timedelta(minutes=5))
    notify(api_client, settings, order, status="in_review", method="credit_card")

    clock.travel(CHECKOUT + CARD_WINDOW)
    release_due()
    assert state_of(order) == "pending_payment"

    clock.travel(CHECKOUT + CARD_WINDOW + MICROSECOND)
    release_due()
    assert state_of(order) == "expired"


@pytest.mark.parametrize(
    "method, voucher_expiry, window",
    [
        ("spei", None, timedelta(hours=4)),
        # Voucher expiry (72 h after creation) plus the 2 h grace.
        ("oxxo", CHECKOUT + timedelta(minutes=5, hours=72), timedelta(hours=72 + 2)),
    ],
)
def test_p9_v09_ttl_boundaries(
    clock, api_client, settings, db, method, voucher_expiry, window
):
    order = checkout_at(clock)
    seen_at = CHECKOUT + timedelta(minutes=5)
    clock.travel(seen_at)
    holds = InventoryReservation.objects.count()

    notify(
        api_client,
        settings,
        order,
        status="pending",
        method=method,
        voucher_expires_at=voucher_expiry,
    )

    # SPEI: 4 h from the `pending` notification. OXXO: the voucher's expiry plus 2 h.
    deadline = (
        seen_at + window if method == "spei" else voucher_expiry + timedelta(hours=2)
    )
    assert Order.objects.get(pk=order.pk).payment_deadline_at == deadline
    assert expires_at(order) == deadline
    assert InventoryReservation.objects.count() == holds  # extended, not recreated

    clock.travel(deadline)
    release_due()
    assert state_of(order) == "pending_payment"

    clock.travel(deadline + MICROSECOND)
    release_due()
    assert state_of(order) == "expired"


def test_a_later_notification_never_shortens_the_window(
    clock, api_client, settings, db
):
    order = checkout_at(clock)
    clock.travel(CHECKOUT + timedelta(minutes=5))
    notify(
        api_client,
        settings,
        order,
        status="pending",
        method="oxxo",
        voucher_expires_at=CHECKOUT + timedelta(hours=72),
    )
    granted = Order.objects.get(pk=order.pk).payment_deadline_at

    notify(api_client, settings, order, status="in_review", method="spei")

    # SPEI would give only 4 h from now: the longer OXXO window stands.
    assert Order.objects.get(pk=order.pk).payment_deadline_at == granted
    assert expires_at(order) == granted


def test_g48_hold_and_deadline_move_together_and_never_diverge(
    clock, api_client, settings, db, caplog
):
    caplog.set_level(logging.WARNING)
    order = checkout_at(clock)
    clock.travel(CHECKOUT + timedelta(minutes=5))
    notify(api_client, settings, order, status="pending", method="spei")

    # Past the card window: the SPEI order is still held and still payable.
    clock.travel(CHECKOUT + CARD_WINDOW + timedelta(minutes=1))
    release_due()

    assert state_of(order) == "pending_payment"
    assert expires_at(order) == Order.objects.get(pk=order.pk).payment_deadline_at
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_g48_guard_failed_is_a_one_line_warning(clock, db, caplog):
    caplog.set_level(logging.WARNING)
    order = checkout_at(clock)
    # A hold that lapses before its order's deadline: the state the guard exists to refuse.
    InventoryReservation.objects.filter(order=order).update(
        expires_at=CHECKOUT + timedelta(minutes=10)
    )
    clock.travel(CHECKOUT + timedelta(minutes=11))

    release_due()

    assert state_of(order) == "pending_payment"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].levelno == logging.WARNING
    assert warnings[0].exc_info is None


def test_p9_v21_voucher_generated_after_checkout_ttl(
    clock, api_client, settings, db, caplog
):
    caplog.set_level(logging.WARNING)
    order = checkout_at(clock)
    # The customer is still on the provider page.
    clock.travel(CHECKOUT + timedelta(minutes=31))
    release_due()
    assert state_of(order) == "expired"

    payment_id = mock_payment_for(
        order,
        status="pending",
        method="oxxo",
        voucher_expires_at=CHECKOUT + timedelta(hours=72),
    )
    body, headers = signed_notification(settings, payment_id)
    assert post_notification(api_client, body, headers).status_code == 200

    # ADR-0046: the order stays expired, a person is alerted, and the voucher is cancelled.
    assert state_of(order) == "expired"
    assert len([r for r in caplog.records if "ALERT" in r.getMessage()]) == 1
    assert MockPaymentProvider().fetch_payment(payment_id).status.value == "cancelled"


def test_late_voucher_cancel_failure_is_retried(
    clock, api_client, settings, db, monkeypatch
):
    """ADR-0046: a provider failure on `cancel_payment` leaves the webhook row for a retry (G7)."""
    from apps.payments.models import WebhookEvent

    order = checkout_at(clock)
    clock.travel(CHECKOUT + timedelta(minutes=31))
    release_due()
    payment_id = mock_payment_for(
        order,
        status="pending",
        method="oxxo",
        voucher_expires_at=CHECKOUT + timedelta(hours=72),
    )
    real_cancel = MockPaymentProvider.cancel_payment
    failures = [ConnectionError("provider timed out")]

    def flaky(self, provider_payment_id):
        if failures:
            raise failures.pop()
        return real_cancel(self, provider_payment_id)

    monkeypatch.setattr(MockPaymentProvider, "cancel_payment", flaky)
    body, headers = signed_notification(settings, payment_id)
    assert post_notification(api_client, body, headers).status_code == 200

    event = WebhookEvent.objects.get()
    assert event.processed_at is None
    assert "ConnectionError" in event.error
    assert MockPaymentProvider().fetch_payment(payment_id).status.value == "pending"

    clock.travel(CHECKOUT + timedelta(minutes=32))
    call_command("process_webhooks")
    event.refresh_from_db()
    assert event.processed_at is not None
    assert state_of(order) == "expired"
    assert MockPaymentProvider().fetch_payment(payment_id).status.value == "cancelled"
