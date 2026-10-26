"""Status mapping: amount guard, already applied, late payment, refunds (SPEC.md 9.4, T9.4)."""

import logging
from datetime import UTC, datetime

import pytest

from apps.payments.mock import MockPaymentProvider
from apps.payments.models import Payment, WebhookEvent
from tests.factories.orders import order_in_state
from tests.factories.payments import (
    mock_payment_for,
    post_notification,
    signed_notification,
)


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def deliver(api_client, settings, order, **payment):
    refunded = payment.get("status") == "refunded"
    payment_id = mock_payment_for(order, **payment)
    if refunded:  # a refund the provider made, for the full amount
        MockPaymentProvider().update_payment(
            payment_id, refunds=[{"id": "mock_ref_x", "amount": "100.00"}]
        )
    body, headers = signed_notification(settings, payment_id)
    assert post_notification(api_client, body, headers).status_code == 200
    assert WebhookEvent.objects.order_by("-pk").first().error == ""
    return Payment.objects.get(provider_payment_id=payment_id)


def alerts(caplog):
    return [r for r in caplog.records if "ALERT" in r.getMessage()]


def events(order):
    return list(order.events.order_by("pk").values_list("event", flat=True))


@pytest.mark.parametrize("offset", [1, -1])
def test_p9_v07_amount_off_by_one_centavo(api_client, settings, db, caplog, offset):
    caplog.set_level(logging.WARNING)
    order = order_in_state("pending_payment")

    payment = deliver(
        api_client, settings, order, amount_cents=order.total_cents + offset
    )

    order.refresh_from_db()
    assert payment.status == "approved"
    assert order.state == "pending_payment"
    assert events(order) == []
    assert len(alerts(caplog)) == 1


def test_approved_with_the_exact_amount_pays_the_order(api_client, settings, db):
    order = order_in_state("pending_payment")

    payment = deliver(api_client, settings, order)

    order.refresh_from_db()
    assert (payment.status, order.state) == ("approved", "paid")
    assert events(order) == ["payment_approved"]
    assert order.events.get().actor == "webhook"


def test_a_second_approval_is_a_no_op(api_client, settings, db):
    order = order_in_state("pending_payment")
    deliver(api_client, settings, order)
    deliver(api_client, settings, order)

    order.refresh_from_db()
    assert order.state == "paid"
    assert events(order) == ["payment_approved", "webhook_no_op"]


def test_late_payment_leaves_an_expired_order_and_alerts(
    api_client, settings, db, caplog
):
    caplog.set_level(logging.WARNING)
    order = order_in_state("expired")

    payment = deliver(api_client, settings, order)

    order.refresh_from_db()
    assert (payment.status, order.state) == ("approved", "expired")
    assert events(order) == []
    assert len(alerts(caplog)) == 1


@pytest.mark.parametrize("status", ["pending", "in_review", "cancelled"])
def test_statuses_that_move_no_order(api_client, settings, db, status):
    order = order_in_state("pending_payment")

    payment = deliver(api_client, settings, order, status=status)

    order.refresh_from_db()
    assert payment.status == ("cancelled" if status == "cancelled" else "pending")
    assert (order.state, events(order)) == ("pending_payment", [])


def test_rejected_records_t4_once(api_client, settings, db):
    order = order_in_state(
        "pending_payment", payment_deadline_at=datetime(2999, 1, 1, tzinfo=UTC)
    )
    payment_id = mock_payment_for(order, status="rejected")
    for _ in range(2):  # two notifications of one payment
        body, headers = signed_notification(settings, payment_id)
        assert post_notification(api_client, body, headers).status_code == 200

    order.refresh_from_db()
    assert order.state == "pending_payment"
    assert events(order) == ["payment_rejected", "webhook_no_op"]


def test_charged_back_alerts_a_human_and_moves_nothing(
    api_client, settings, db, caplog
):
    caplog.set_level(logging.WARNING)
    order = order_in_state("paid")

    payment = deliver(api_client, settings, order, status="charged_back")

    order.refresh_from_db()
    assert (payment.status, order.state, events(order)) == ("charged_back", "paid", [])
    assert len(alerts(caplog)) == 1


def test_refund_notification_after_an_admin_refund_converges(api_client, settings, db):
    order = order_in_state("paid")
    deliver(api_client, settings, order, status="refunded")
    deliver(api_client, settings, order, status="refunded")

    order.refresh_from_db()
    assert order.state == "refunded"
    assert events(order) == ["refund_issued", "webhook_no_op"]
