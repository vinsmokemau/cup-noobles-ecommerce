"""Payment contract scenarios PAY-01 to PAY-19 (SPEC.md 9.13, T9.13a and T9.13b).

Each scenario is written against `PaymentDriver` and goes through the real webhook endpoint, real
`webhook_event` rows and the real state machine. Only the driver differs between providers.
Sockets stay disabled (CR-41).
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.core.management import call_command
from django.db import connections
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core import providers
from apps.inventory.models import InventoryReservation, StockItem, StockLedger
from apps.notifications.models import EmailOutbox
from apps.orders.models import Order
from apps.payments.base import RefundNotSupported
from apps.payments.devtools import delivery, replay
from apps.payments.mock import MockPaymentProvider
from apps.payments.models import Payment, WebhookEvent
from apps.payments.refunds import RefundRejected, refund_payment
from tests.contract.payments.conftest import CHECKOUT
from tests.contract.payments.driver import Outcome
from tests.factories.orders import cart_with, place_order

CARD_WINDOW = timedelta(minutes=30)
GRACE = timedelta(hours=2)  # D6: an OXXO order outlives its voucher by this much (9.5)


def play(driver, order, outcome, **opts):
    """Check out, play `outcome`, and deliver what the provider queued. Returns the payment id."""
    payment_id = driver.complete(driver.checkout(order), outcome, **opts)
    driver.deliver_pending_notifications()
    return payment_id


def reload(order):
    return Order.objects.get(pk=order.pk)


def payments(order):
    """The provider's payments for `order`. The `initiated` row that checkout opens for the
    preference stays beside them (it has no provider payment id)."""
    return Payment.objects.filter(order=order).exclude(status="initiated")


def holds(order):
    return InventoryReservation.objects.filter(order=order)


def release_due():
    call_command("expire_reservations")


def event_names(order):
    return list(order.events.order_by("pk").values_list("event", flat=True))


def test_pay_01_card_approved(driver, order, variant):
    play(driver, order, Outcome.APPROVED)

    assert reload(order).state == "paid"
    payment = payments(order).get()
    assert (payment.status, payment.method) == ("approved", "credit_card")
    assert payment.amount_cents == order.total_cents
    # Stock committed: the units left the shelf and are no longer held.
    assert {r.state for r in holds(order)} == {"committed"}
    item = StockItem.objects.get(variant=variant)
    assert (item.on_hand, item.reserved) == (10 - 2, 0)
    sale = StockLedger.objects.get(order=order, reason="sale_online")
    assert (sale.delta, sale.balance_after) == (-2, 8)
    # The confirmation email is queued, once.
    assert (
        EmailOutbox.objects.filter(order=order, template="order_confirmation").count()
        == 1
    )


def test_pay_02_approved_with_installments(driver, order, variant):
    play(driver, order, Outcome.APPROVED_IN_INSTALLMENTS, installments=6)

    assert reload(order).state == "paid"
    payment = payments(order).get()
    assert (payment.status, payment.installments) == ("approved", 6)
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockLedger.objects.filter(order=order, reason="sale_online").count() == 1
    assert EmailOutbox.objects.filter(
        order=order, template="order_confirmation"
    ).exists()


def test_pay_03_oxxo_pending(driver, order, shop):
    payment_id = play(driver, order, Outcome.OXXO_VOUCHER)

    # Not paid yet; the voucher is stored and shown.
    assert reload(order).state == "pending_payment"
    payment = payments(order).get()
    assert (payment.status, payment.method) == ("pending", "oxxo")
    assert payment.provider_payment_id == payment_id
    assert payment.voucher_url
    assert payment.voucher_expires_at is not None
    assert EmailOutbox.objects.filter(order=order, template="oxxo_voucher").exists()
    # The holds and the deadline stretch to the voucher's expiry plus the grace, together.
    deadline = payment.voucher_expires_at + GRACE
    assert reload(order).payment_deadline_at == deadline
    assert {r.expires_at for r in holds(order)} == {deadline}
    assert {r.state for r in holds(order)} == {"held"}

    # The card window is long gone, and the job still leaves the holds alone.
    shop.travel(CHECKOUT + CARD_WINDOW + timedelta(minutes=1))
    release_due()
    assert reload(order).state == "pending_payment"
    assert {r.state for r in holds(order)} == {"held"}


def test_pay_04_oxxo_pending_then_paid(driver, order, variant):
    payment_id = play(driver, order, Outcome.OXXO_VOUCHER)
    assert reload(order).state == "pending_payment"

    play_voucher = driver.complete(
        driver.checkout(order), Outcome.VOUCHER_PAID, payment_id=payment_id
    )
    driver.deliver_pending_notifications()

    # One payment, two notifications (`pending`, then `approved`), both processed.
    assert play_voucher == payment_id
    assert reload(order).state == "paid"
    payment = payments(order).get()
    assert (payment.status, payment.provider_payment_id) == ("approved", payment_id)
    events = WebhookEvent.objects.filter(topic="payment")
    assert events.count() == 2
    assert not events.filter(processed_at__isnull=True).exists()
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockItem.objects.get(variant=variant).on_hand == 10 - 2
    assert event_names(order).count("payment_approved") == 1


def test_pay_05_oxxo_voucher_expires(driver, order, variant, shop):
    payment_id = play(driver, order, Outcome.OXXO_VOUCHER)
    deadline = reload(order).payment_deadline_at

    driver.complete(
        driver.checkout(order), Outcome.VOUCHER_LAPSED, payment_id=payment_id
    )
    driver.deliver_pending_notifications()

    # The provider ends the voucher; the order waits out its grace, then the job expires it.
    assert payments(order).get().status == "cancelled"
    assert reload(order).state == "pending_payment"
    shop.travel(deadline + timedelta(minutes=1))
    release_due()

    assert reload(order).state == "expired"
    assert {r.state for r in holds(order)} == {"released"}
    item = StockItem.objects.get(variant=variant)
    assert (item.on_hand, item.reserved) == (10, 0)
    assert not StockLedger.objects.filter(order=order, reason="sale_online").exists()
    assert EmailOutbox.objects.filter(order=order, template="order_expired").exists()


def test_pay_06_spei_pending_then_paid(driver, order, variant, settings):
    payment_id = play(driver, order, Outcome.SPEI_TRANSFER)

    payment = payments(order).get()
    assert (payment.status, payment.method) == ("pending", "spei")
    assert reload(order).state == "pending_payment"
    # SPEI deadlines: the holds and the order move to the SPEI window together.
    deadline = CHECKOUT + timedelta(hours=settings.RESERVATION_TTL_SPEI_HOURS)
    assert reload(order).payment_deadline_at == deadline
    assert {r.expires_at for r in holds(order)} == {deadline}

    driver.complete(driver.checkout(order), Outcome.VOUCHER_PAID, payment_id=payment_id)
    driver.deliver_pending_notifications()

    assert reload(order).state == "paid"
    assert payments(order).get().status == "approved"
    events = WebhookEvent.objects.filter(topic="payment")
    assert events.count() == 2
    assert not events.filter(processed_at__isnull=True).exists()
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockItem.objects.get(variant=variant).on_hand == 10 - 2


def test_pay_07_rejected_then_retried(driver, order, variant):
    play(driver, order, Outcome.REJECTED)

    # The order stays open, with its stock held.
    assert reload(order).state == "pending_payment"
    assert payments(order).get().status == "rejected"
    assert {r.state for r in holds(order)} == {"held"}
    assert "payment_rejected" in event_names(order)

    # Before the deadline the customer pays again, on a fresh checkout.
    play(driver, order, Outcome.APPROVED)

    assert reload(order).state == "paid"
    assert sorted(payments(order).values_list("status", flat=True)) == [
        "approved",
        "rejected",
    ]
    assert {r.state for r in holds(order)} == {"committed"}
    assert StockItem.objects.get(variant=variant).on_hand == 10 - 2


def test_pay_08_no_payment_then_expiry(driver, order, variant, shop):
    deadline = reload(order).payment_deadline_at

    # The customer leaves the provider's page: nothing is paid, nothing is sent.
    assert play(driver, order, Outcome.ABANDONED) == ""
    assert not WebhookEvent.objects.exists()
    shop.travel(deadline + timedelta(minutes=1))
    release_due()

    assert reload(order).state == "expired"
    assert {r.state for r in holds(order)} == {"released"}
    item = StockItem.objects.get(variant=variant)
    assert (item.on_hand, item.reserved) == (10, 0)
    assert EmailOutbox.objects.filter(order=order, template="order_expired").exists()


# --- PAY-09 to PAY-19: idempotency, security and recovery (T9.13b) ---


def alerts(caplog):
    return [r for r in caplog.records if "ALERT" in r.getMessage()]


def post(request):
    """POST a `(body, headers)` pair to the webhook; returns the status code."""
    body, headers = request
    return (
        APIClient()
        .post(
            delivery.WEBHOOK_PATH,
            data=body,
            content_type="application/json",
            headers=headers,
        )
        .status_code
    )


def unsent_notification(driver, order, outcome=Outcome.APPROVED, **opts):
    """Play `outcome` and keep the notification back. Returns it as the unsaved `webhook_event`
    row `replay` rebuilds a request from, so a test can send it signed, tampered or stale."""
    payment_id = driver.complete(driver.checkout(order), outcome, **opts)
    provider = providers.payment_provider()
    (queued,) = provider.queued_notifications()
    return WebhookEvent(
        provider=provider.code,
        topic=queued["type"],
        external_id=queued["id"],
        payload={
            "ref": {
                "topic": queued["type"],
                "notification_id": queued["id"],
                "resource_id": payment_id,
            },
            "body": {
                "id": queued["id"],
                "type": queued["type"],
                "data": queued["data"],
            },
        },
    )


@pytest.mark.django_db(transaction=True)
def test_pay_09_same_notification_five_times_concurrently(driver, order):
    event = unsent_notification(driver, order)
    count = 5
    barrier = Barrier(count, timeout=30)

    def deliver_once():
        try:
            request = replay.build_request(event)
            barrier.wait()
            return post(request)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = [pool.submit(deliver_once) for _ in range(count)]
        statuses = [future.result() for future in futures]

    # Every delivery is acknowledged; exactly one did the work.
    assert statuses == [200] * count
    assert WebhookEvent.objects.filter(topic="payment").count() == 1
    assert payments(order).count() == 1
    assert reload(order).state == "paid"
    assert event_names(order).count("payment_approved") == 1
    assert StockLedger.objects.filter(order=order, reason="sale_online").count() == 1


def test_pay_10_replay_of_a_processed_notification(driver, order):
    play(driver, order, Outcome.APPROVED)
    event = WebhookEvent.objects.get(topic="payment")
    before = event_names(order)

    assert post(replay.build_request(event)) == 200

    assert WebhookEvent.objects.filter(topic="payment").count() == 1
    assert event_names(order) == before
    assert payments(order).count() == 1
    assert reload(order).state == "paid"


def test_pay_11_tampered_signature(driver, order):
    event = unsent_notification(driver, order)
    before = event_names(order)

    assert post(replay.build_request(event, corrupt=True)) == 401

    stored = WebhookEvent.objects.get()
    assert stored.signature_ok is False
    assert stored.processed_at is None
    assert reload(order).state == "pending_payment"
    assert not payments(order).exists()
    assert event_names(order) == before


def test_pay_12_stale_timestamp(driver, order):
    event = unsent_notification(driver, order)

    assert post(replay.build_request(event, ts=replay.stale_ts())) == 401

    assert not WebhookEvent.objects.filter(signature_ok=True).exists()
    assert reload(order).state == "pending_payment"
    assert not payments(order).exists()

    # The same notification, signed now, is still accepted.
    assert post(replay.build_request(event)) == 200
    assert reload(order).state == "paid"


@pytest.mark.parametrize("offset", [1, -1])
def test_pay_13_amount_mismatch(driver, order, caplog, offset):
    caplog.set_level(logging.WARNING)

    play(driver, order, Outcome.APPROVED, amount_cents=order.total_cents + offset)

    payment = payments(order).get()
    assert (payment.status, payment.amount_cents) == (
        "approved",
        order.total_cents + offset,
    )
    assert reload(order).state == "pending_payment"
    assert "payment_approved" not in event_names(order)
    assert {r.state for r in holds(order)} == {"held"}
    assert len(alerts(caplog)) == 1


def test_pay_14_dropped_notification_is_reconciled(driver, order, shop):
    # The provider takes the payment and its notification never arrives.
    driver.complete(driver.checkout(order), Outcome.APPROVED)
    assert reload(order).state == "pending_payment"

    shop.travel(CHECKOUT + timedelta(minutes=16))
    call_command("reconcile_payments")

    assert reload(order).state == "paid"
    assert payments(order).get().status == "approved"
    assert not WebhookEvent.objects.exists()

    # The late delivery finds nothing left to do.
    driver.deliver_pending_notifications()

    assert reload(order).state == "paid"
    assert event_names(order).count("payment_approved") == 1
    assert event_names(order).count("webhook_no_op") == 1
    assert payments(order).count() == 1
    assert StockLedger.objects.filter(order=order, reason="sale_online").count() == 1


def test_pay_15_payment_approved_after_the_order_expired(
    driver, order, variant, shop, caplog
):
    caplog.set_level(logging.WARNING)
    deadline = reload(order).payment_deadline_at
    # The customer pays at the last second; the notification is slow.
    driver.complete(driver.checkout(order), Outcome.APPROVED)
    shop.travel(deadline + timedelta(minutes=1))
    release_due()
    assert reload(order).state == "expired"

    driver.deliver_pending_notifications()

    assert payments(order).get().status == "approved"
    assert reload(order).state == "expired"
    assert {r.state for r in holds(order)} == {"released"}
    assert StockItem.objects.get(variant=variant).on_hand == 10
    assert not StockLedger.objects.filter(order=order, reason="sale_online").exists()
    assert len(alerts(caplog)) == 1


def test_pay_16_full_partial_and_over_refund(driver, order, variant, monkeypatch):
    calls = []
    original = MockPaymentProvider.refund

    def spy(self, payment, amount_cents):
        calls.append(amount_cents)
        return original(self, payment, amount_cents)

    monkeypatch.setattr(MockPaymentProvider, "refund", spy)
    partial_order = place_order(cart_with((variant, 1)))
    play(driver, order, Outcome.APPROVED)
    play(driver, partial_order, Outcome.APPROVED)
    full, partial = payments(order).get(), payments(partial_order).get()

    # Full: the whole payment goes back and the order is refunded.
    moved = refund_payment(full.pk, actor="staff:1")
    driver.deliver_pending_notifications()
    full.refresh_from_db()
    assert (moved.state, full.status, full.refunded_cents) == (
        "refunded",
        "refunded",
        full.amount_cents,
    )
    assert reload(order).state == "refunded"

    # Partial: the payment is partially refunded and the order stays fulfillable.
    moved = refund_payment(partial.pk, actor="staff:1", amount_cents=1000)
    driver.deliver_pending_notifications()
    partial.refresh_from_db()
    assert (moved.state, partial.status, partial.refunded_cents) == (
        "paid",
        "partially_refunded",
        1000,
    )
    assert reload(partial_order).state == "paid"
    assert event_names(partial_order).count("partial_refund_issued") == 1

    # Over-refund: rejected before the provider is called, and nothing changes.
    sent = list(calls)
    with pytest.raises(RefundRejected):
        refund_payment(
            partial.pk, actor="staff:1", amount_cents=partial.amount_cents - 999
        )
    assert calls == sent
    partial.refresh_from_db()
    assert partial.refunded_cents == 1000


def test_pay_17_oxxo_refund_is_manual(driver, order, admin_client):
    payment_id = play(driver, order, Outcome.OXXO_VOUCHER)
    driver.complete(driver.checkout(order), Outcome.VOUCHER_PAID, payment_id=payment_id)
    driver.deliver_pending_notifications()
    payment = payments(order).get()
    assert (reload(order).state, payment.method) == ("paid", "oxxo")

    with pytest.raises(RefundNotSupported):
        refund_payment(payment.pk, actor="staff:1")

    # The admin shows the warning and offers the manual refund.
    response = admin_client.post(
        reverse("admin:orders_order_event", args=[order.pk]),
        {"event": "refund_issued"},
        follow=True,
    )
    shown = [str(message) for message in response.context["messages"]]
    assert len(shown) == 1 and "OXXO" in shown[0]
    assert "Registrar reembolso manual" in response.content.decode()
    assert reload(order).state == "paid"

    moved = refund_payment(payment.pk, actor="staff:1", manual_note="SPEI 123")

    payment.refresh_from_db()
    assert (moved.state, payment.status) == ("refunded", "refunded")
    assert order.events.get(event="refund_issued").payload["manual"] is True


def test_pay_18_chargeback_alerts_and_moves_nothing(driver, order, caplog):
    caplog.set_level(logging.WARNING)
    payment_id = play(driver, order, Outcome.APPROVED)
    before = event_names(order)

    call_command("mock_payments", "chargeback", payment_id)
    driver.deliver_pending_notifications()

    assert payments(order).get().status == "charged_back"
    assert reload(order).state == "paid"
    assert event_names(order) == before
    assert len(alerts(caplog)) == 1


def test_pay_19_notification_for_an_unknown_order(driver, order, caplog):
    caplog.set_level(logging.WARNING)
    payment_id = driver.complete(driver.checkout(order), Outcome.APPROVED)
    providers.payment_provider().update_payment(
        payment_id, external_reference=str(uuid.uuid4())
    )

    driver.deliver_pending_notifications()

    stored = WebhookEvent.objects.get(topic="payment")
    assert stored.processed_at is not None
    assert stored.error
    assert len(alerts(caplog)) == 1
    assert reload(order).state == "pending_payment"
    assert not payments(order).exists()
