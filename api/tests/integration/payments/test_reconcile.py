"""`reconcile_payments`: the safety net for dropped notifications (SPEC.md 9.7, T9.7)."""

import logging
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from apps.orders.models import Order
from apps.payments.base import PaymentNotFound
from apps.payments.models import Payment
from tests.factories.orders import order_in_state
from tests.factories.payments import mock_payment_for

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def run_reconcile() -> str:
    out = StringIO()
    call_command("reconcile_payments", stdout=out)
    return out.getvalue()


def aged(minutes, **fields):
    return order_in_state(
        "pending_payment", created_at=NOW - timedelta(minutes=minutes), **fields
    )


@pytest.fixture(autouse=True)
def _now(clock):
    clock.travel(NOW)


def test_a_dropped_approval_pays_the_order(db):
    order = aged(20)
    payment_id = mock_payment_for(order, status="approved")

    assert "1 orders checked, 1 payments found, 0 failed" in run_reconcile()

    order.refresh_from_db()
    assert order.state == "paid"
    assert Payment.objects.get().provider_payment_id == payment_id


def test_orders_younger_than_fifteen_minutes_are_left_alone(db):
    young = aged(14)
    mock_payment_for(young, status="approved")

    assert "0 orders checked" in run_reconcile()

    young.refresh_from_db()
    assert young.state == "pending_payment"
    assert Payment.objects.count() == 0


def test_the_fifteen_minute_boundary_is_exclusive(db):
    exactly = aged(15)
    mock_payment_for(exactly, status="approved")

    assert "0 orders checked" in run_reconcile()


def test_only_pending_payment_orders_are_checked(db):
    paid = order_in_state("paid", created_at=NOW - timedelta(hours=2))
    mock_payment_for(paid, status="approved")

    assert "0 orders checked" in run_reconcile()
    assert Payment.objects.count() == 0


def test_an_order_without_payments_stays_pending(db):
    order = aged(30)

    assert "1 orders checked, 0 payments found" in run_reconcile()

    order.refresh_from_db()
    assert order.state == "pending_payment"


def test_running_twice_moves_the_order_once(db):
    order = aged(20)
    mock_payment_for(order, status="approved")

    run_reconcile()
    out = run_reconcile()

    assert "0 orders checked" in out  # it is paid now, so the second run never sees it
    assert order.events.filter(event="payment_approved").count() == 1


def test_a_pending_oxxo_payment_extends_the_deadline(db):
    deadline = NOW + timedelta(minutes=5)
    order = aged(25, payment_deadline_at=deadline)
    mock_payment_for(
        order,
        status="pending",
        method="oxxo",
        voucher_url="https://mock.example/voucher",
        voucher_expires_at=NOW + timedelta(hours=48),
    )

    run_reconcile()

    order.refresh_from_db()
    assert order.state == "pending_payment"
    assert order.payment_deadline_at > deadline


def test_one_failing_order_does_not_stop_the_rest(db, monkeypatch, caplog):
    from apps.payments.mock import MockPaymentProvider

    broken = aged(40)
    healthy = aged(30)
    mock_payment_for(healthy, status="approved")
    real = MockPaymentProvider.find_payments

    def find(self, external_reference):
        if external_reference == str(broken.public_id):
            raise PaymentNotFound("down")
        return real(self, external_reference)

    monkeypatch.setattr(MockPaymentProvider, "find_payments", find)
    caplog.set_level(logging.ERROR)

    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="1 orders could not be reconciled"):
        run_reconcile()

    assert Order.objects.get(pk=healthy.pk).state == "paid"
    assert any(broken.number in r.getMessage() for r in caplog.records)


def test_p9_v04_dropped_reconciled_then_late_delivery(db, api_client, monkeypatch):
    from apps.core import providers
    from apps.payments.devtools import delivery

    def in_process(base_url):
        def send(body, headers):
            return api_client.post(
                delivery.WEBHOOK_PATH,
                data=body,
                content_type="application/json",
                headers=headers,
            ).status_code

        return send

    monkeypatch.setattr(delivery, "http_transport", in_process)
    order = aged(20)
    provider = providers.payment_provider()
    provider.create_checkout(order)

    call_command("mock_payments", "drop", order.number, "--outcome", "approve")
    assert provider.queued_notifications() == []  # nothing for the webhook to see

    run_reconcile()
    order.refresh_from_db()
    assert order.state == "paid"
    payment = Payment.objects.get()

    # The notification that was lost turns up late.
    provider.queue_notification(payment.provider_payment_id)
    call_command("mock_payments", "deliver", "--once", stdout=StringIO())

    names = list(order.events.order_by("pk").values_list("event", flat=True))
    assert names == ["payment_approved", "webhook_no_op"]
    assert Order.objects.get(pk=order.pk).state == "paid"
    assert provider.queued_notifications() == []
