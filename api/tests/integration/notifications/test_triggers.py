from datetime import UTC, datetime, timedelta

import pytest

from apps.inventory import services
from apps.notifications.models import EmailOutbox
from apps.orders.models import Order
from apps.orders.state_machine import apply_event
from apps.payments.models import Payment
from tests.factories.inventory import stocked_variant
from tests.factories.orders import (
    ShipmentFactory,
    cart_with,
    order_in_state,
    order_through_checkout,
    place_order,
)
from tests.factories.payments import (
    PaymentFactory,
    mock_payment_for,
    post_notification,
    signed_notification,
)

pytestmark = pytest.mark.django_db

VOUCHER = "http://localhost:8080/dev/payments/voucher/1/"


def _paid_order():
    order = order_in_state("paid")
    PaymentFactory(
        order=order,
        status="approved",
        amount_cents=order.total_cents,
        provider_payment_id=f"mock_pay_{order.pk}",
    )
    return order


def _t2(api_client, settings):
    order = place_order(cart_with((stocked_variant(5), 1)))
    return order, lambda: apply_event(
        order.pk, "payment_approved", amount_cents=order.total_cents
    )


def _pending_oxxo(api_client, settings):
    order = order_in_state(
        "pending_payment", payment_deadline_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    services.reserve(order, [(stocked_variant(5), 1)], ttl=timedelta(minutes=30))

    def notify():
        payment_id = mock_payment_for(
            order,
            status="pending",
            method="oxxo",
            voucher_url=VOUCHER,
            voucher_expires_at=datetime.now(UTC) + timedelta(days=3),
        )
        body, headers = signed_notification(settings, payment_id)
        assert post_notification(api_client, body, headers).status_code == 200

    return order, notify


def _t5(api_client, settings):
    order = order_through_checkout("pending_payment")
    Order.objects.filter(pk=order.pk).update(
        payment_deadline_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    return order, lambda: apply_event(order.pk, "deadline_passed")


def _t10(api_client, settings):
    order = order_through_checkout("preparing")
    ShipmentFactory(order=order)
    return order, lambda: apply_event(order.pk, "shipment_created")


def _t6(api_client, settings):
    order = order_through_checkout("pending_payment")
    return order, lambda: apply_event(order.pk, "cancelled_by_customer")


def _t16(api_client, settings):
    order = _paid_order()
    return order, lambda: apply_event(
        order.pk, "cancelled_by_staff", actor="staff:1", cancel_reason="Sin stock"
    )


def _refund(event, share):
    def trigger(api_client, settings):
        order = _paid_order()
        payment = Payment.objects.get(order=order)
        return order, lambda: apply_event(
            order.pk,
            event,
            payment_id=payment.pk,
            refunded_cents=payment.amount_cents // share,
        )

    return trigger


TRIGGERS = {
    "T2": (_t2, "order_confirmation"),
    "pending_oxxo": (_pending_oxxo, "oxxo_voucher"),
    "T5": (_t5, "order_expired"),
    "T10": (_t10, "order_shipped"),
    "T6": (_t6, "order_cancelled"),
    "T16": (_t16, "order_cancelled"),
    "T17": (_refund("refund_issued", 1), "refund_issued"),
    "T18": (_refund("partial_refund_issued", 2), "refund_issued"),
}


@pytest.mark.parametrize("trigger", TRIGGERS)
def test_p11_v09_each_trigger_queues_its_template(
    trigger, dev_defaults, api_client, settings
):
    build, template = TRIGGERS[trigger]
    order, fire = build(api_client, settings)
    before = set(EmailOutbox.objects.filter(order=order).values_list("pk", flat=True))

    fire()

    queued = EmailOutbox.objects.filter(order=order).exclude(pk__in=before)
    assert [row.template for row in queued] == [template]
    assert queued.get().to_email == order.email


def test_a_second_partial_refund_queues_its_own_email(dev_defaults):
    order = _paid_order()
    payment = Payment.objects.get(order=order)
    half = payment.amount_cents // 2

    apply_event(
        order.pk,
        "partial_refund_issued",
        payment_id=payment.pk,
        refunded_cents=half // 2,
    )
    apply_event(
        order.pk, "partial_refund_issued", payment_id=payment.pk, refunded_cents=half
    )

    rows = EmailOutbox.objects.filter(order=order, template="refund_issued").order_by(
        "pk"
    )
    assert [
        (r.context["refund_cents"], r.context["refunded_total_cents"]) for r in rows
    ] == [
        (half // 2, half // 2),
        (half - half // 2, half),
    ]
