"""The `mock_payments` dev commands (SPEC.md 9.12a)."""

import json
import logging
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.core import providers
from apps.inventory.models import InventoryReservation
from apps.orders.models import Order
from apps.payments.devtools import delivery
from apps.payments.models import Payment
from tests.factories.inventory import holding_order, stocked_variant
from tests.factories.orders import STAND_IN_ADDRESS, order_in_state


def run(*args) -> str:
    out = StringIO()
    call_command("mock_payments", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def provider():
    return providers.payment_provider()


@pytest.fixture
def order(db, provider):
    order = order_in_state("pending_payment")
    provider.create_checkout(order)
    return order


@pytest.fixture
def in_process(monkeypatch, api_client):
    def transport_for(base_url):
        def send(body, headers):
            return api_client.post(
                delivery.WEBHOOK_PATH,
                data=body,
                content_type="application/json",
                headers=headers,
            ).status_code

        return send

    monkeypatch.setattr(delivery, "http_transport", transport_for)


def only_payment(provider, order):
    (stored,) = provider.find_payments(str(order.public_id))
    return stored


def test_approve_records_queues_and_pays(order, provider, in_process):
    run("approve", order.number)
    assert len(provider.queued_notifications()) == 1

    run("deliver", "--once")

    order.refresh_from_db()
    assert order.state == "paid"


def test_approve_with_installments(order, in_process):
    run("approve", order.number, "--installments", "6")
    run("deliver", "--once")

    assert Payment.objects.get().installments == 6


def test_approve_rejects_an_installment_plan_the_checkout_does_not_offer(order):
    with pytest.raises(CommandError, match="Installments must be one of"):
        run("approve", order.number, "--installments", "7")


def test_approve_with_a_mismatched_amount_trips_the_amount_guard(
    order, in_process, caplog
):
    caplog.set_level(logging.WARNING)
    run("approve", order.number, "--amount-cents", str(order.total_cents + 1))
    run("deliver", "--once")

    order.refresh_from_db()
    assert order.state == "pending_payment"
    assert Payment.objects.get().status == "approved"
    assert any("ALERT" in r.getMessage() for r in caplog.records)


def test_reject_leaves_the_order_pending(order, in_process):
    run("reject", order.number)
    run("deliver", "--once")

    order.refresh_from_db()
    assert order.state == "pending_payment"
    assert Payment.objects.get().status == "rejected"


@pytest.mark.parametrize(
    ("command", "state", "status"),
    [
        ("pay-voucher", "paid", "approved"),
        ("expire-voucher", "pending_payment", "cancelled"),
    ],
)
def test_voucher_commands(order, provider, in_process, command, state, status):
    run("drop", order.number, "--outcome", "pending")
    payment_id = only_payment(provider, order).provider_payment_id

    run(command, payment_id)
    run("deliver", "--once")

    order.refresh_from_db()
    assert (order.state, Payment.objects.get().status) == (state, status)


def test_voucher_commands_refuse_a_card_payment(order, provider):
    run("approve", order.number)
    payment_id = only_payment(provider, order).provider_payment_id

    with pytest.raises(CommandError, match="not an OXXO or SPEI"):
        run("pay-voucher", payment_id)


@pytest.mark.parametrize("outcome", ["approve", "reject", "pending"])
def test_drop_records_without_a_notification(order, provider, outcome):
    run("drop", order.number, "--outcome", outcome)

    assert provider.queued_notifications() == []
    expected = {"approve": "approved", "reject": "rejected", "pending": "pending"}
    assert only_payment(provider, order).status.value == expected[outcome]


def test_chargeback_alerts_and_moves_nothing(order, provider, in_process, caplog):
    caplog.set_level(logging.WARNING)
    run("approve", order.number)
    run("deliver", "--once")
    payment_id = only_payment(provider, order).provider_payment_id

    run("chargeback", payment_id)
    run("deliver", "--once")

    order.refresh_from_db()
    assert order.state == "paid"
    assert any("charged back" in r.getMessage() for r in caplog.records)


def test_expire_order_expires_the_order_and_releases_its_holds(db):
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2, ttl=timedelta(hours=1))
    Order.objects.filter(pk=order.pk).update(
        state="pending_payment",
        shipping_address=STAND_IN_ADDRESS,
        payment_deadline_at=timezone.now() + timedelta(hours=1),
    )

    run("expire-order", order.number)

    order.refresh_from_db()
    assert order.state == "expired"
    assert not InventoryReservation.objects.filter(
        order=order, state=InventoryReservation.State.HELD
    ).exists()


def test_list_shows_one_orders_records_and_reset_clears_them(order, provider):
    other = order_in_state("pending_payment")
    provider.create_checkout(other)
    run("approve", order.number)

    shown = json.loads(run("list", "--order", order.number))
    assert [p["order_number"] for p in shown["preferences"]] == [order.number]
    assert len(shown["payments"]) == 1
    assert len(json.loads(run("list"))["preferences"]) == 2

    assert "records removed" in run("reset")
    assert json.loads(run("list")) == {
        "preferences": [],
        "payments": [],
        "notifications": [],
    }


def test_an_unknown_order_is_an_error(db):
    with pytest.raises(CommandError, match="There is no order CN-0"):
        run("approve", "CN-0")


def test_an_order_without_a_checkout_is_an_error(db):
    order = order_in_state("pending_payment")
    with pytest.raises(CommandError, match="no checkout"):
        run("reject", order.number)


def test_refuses_to_run_unless_dev_tools_are_enabled(settings, db):
    settings.DEV_TOOLS_ENABLED = False
    with pytest.raises(CommandError, match="DEV_TOOLS_ENABLED"):
        run("list")
