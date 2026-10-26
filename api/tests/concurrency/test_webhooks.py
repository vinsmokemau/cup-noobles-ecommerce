"""A webhook against reconciliation (SPEC.md 9.7, G14, ADR-0047) and against itself (9.12b)."""

from datetime import UTC, datetime
from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.payments.devtools import delivery
from apps.payments.management.commands.reconcile_payments import reconcile_order
from apps.payments.models import WebhookEvent
from apps.payments.webhooks import process_webhook_event
from tests.concurrency import run_concurrently  # type: ignore[attr-defined]  # tests/concurrency/ is also a directory
from tests.factories.orders import order_in_state
from tests.factories.payments import WebhookEventFactory, mock_payment_for

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]


def test_p9_v14_webhook_vs_reconcile_race(clock):
    clock.travel(datetime(2026, 10, 26, 12, 0, tzinfo=UTC))
    order = order_in_state(
        "pending_payment", created_at=datetime(2026, 10, 26, 11, 0, tzinfo=UTC)
    )
    payment_id = mock_payment_for(order, status="approved")
    event = WebhookEventFactory(
        provider="mock",
        external_id="mock_ntf_race",
        payload={
            "ref": {
                "topic": "payment",
                "notification_id": "mock_ntf_race",
                "resource_id": payment_id,
            }
        },
    )

    def racer(index):
        if index == 0:
            return process_webhook_event(event.pk)
        return reconcile_order(Order.objects.get(pk=order.pk))

    outcomes = run_concurrently(racer, 2)

    assert [o.error for o in outcomes] == [None, None]
    order.refresh_from_db()
    assert order.state == "paid"
    events = order.events.all()
    assert events.filter(event="payment_approved").count() == 1
    # The loser is recorded as a no-op, not raised as IllegalTransition (G14's resolution).
    assert events.filter(event="webhook_no_op").count() <= 1


def test_p9_v05_duplicate_command_concurrent(monkeypatch):
    def transport_for(base_url, path=delivery.WEBHOOK_PATH):
        def send(body, headers):
            return (
                APIClient()
                .post(path, data=body, content_type="application/json", headers=headers)
                .status_code
            )

        return send

    monkeypatch.setattr(delivery, "http_transport", transport_for)
    order = order_in_state("pending_payment")
    payment_id = mock_payment_for(order, status="approved")
    event = WebhookEventFactory(
        provider="mock",
        external_id="mock_ntf_dup",
        payload={
            "ref": {
                "topic": "payment",
                "notification_id": "mock_ntf_dup",
                "resource_id": payment_id,
            },
            "body": {
                "id": "mock_ntf_dup",
                "type": "payment",
                "data": {"id": payment_id},
            },
        },
    )
    out = StringIO()

    call_command(
        "webhooks",
        "duplicate",
        str(event.pk),
        "--count",
        "5",
        "--concurrent",
        stdout=out,
    )

    assert "5 deliveries -> 5 x 200" in out.getvalue()
    (row,) = WebhookEvent.objects.filter(external_id="mock_ntf_dup")
    assert row.processed_at is not None
    assert row.attempts == 1  # the four others short-circuited before any processing
    order.refresh_from_db()
    assert order.state == "paid"
    assert order.events.filter(event="payment_approved").count() == 1
