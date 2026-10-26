"""A webhook against reconciliation (SPEC.md 9.7, G14)."""

from datetime import UTC, datetime

import pytest

from apps.orders.models import Order
from apps.payments.management.commands.reconcile_payments import reconcile_order
from apps.payments.webhooks import process_webhook_event
from tests.concurrency import run_concurrently  # type: ignore[attr-defined]  # tests/concurrency/ is also a directory
from tests.factories.orders import order_in_state
from tests.factories.payments import WebhookEventFactory, mock_payment_for

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]


# G14 is still open (SPEC.md 2.4). The test follows its proposed resolution, and T9.4's mapping
# already behaves that way, so it passes today: a strict xfail would fail the run (XPASS).
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
