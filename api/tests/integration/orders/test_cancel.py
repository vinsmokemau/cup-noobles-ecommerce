"""Staff cancellation (SPEC.md 8.A T16, T8.1)."""

import json

import pytest

from apps.inventory import services as inventory
from apps.inventory.models import StockItem, StockLedger
from apps.orders.models import Order
from apps.orders.state_machine import GuardFailed, apply_event
from tests.factories.inventory import (
    assert_stock_integrity,
    holding_order,
    stocked_variant,
)
from tests.factories.orders import STAND_IN_ADDRESS, order_in_state
from tests.factories.payments import PaymentFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("state", ["paid", "preparing"])
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_p8_v16_staff_cancel_requires_reason(state, reason):
    order = order_in_state(state)
    kwargs = {} if reason is None else {"cancel_reason": reason}
    with pytest.raises(GuardFailed):
        apply_event(order.pk, "cancelled_by_staff", actor="staff:1", **kwargs)
    order.refresh_from_db()
    assert order.state == state
    assert order.cancel_reason == ""
    assert not order.events.exists()


@pytest.mark.parametrize("state", ["paid", "preparing"])
def test_p8_v16_staff_cancel_with_reason_cancels(state):
    order = order_in_state(state)
    result = apply_event(
        order.pk, "cancelled_by_staff", actor="staff:1", cancel_reason="Sin stock"
    )
    assert (result.state, result.cancel_reason) == ("cancelled", "Sin stock")
    assert result.cancelled_at is not None
    event = result.events.get()
    assert (event.from_state, event.to_state, event.actor) == (
        state,
        "cancelled",
        "staff:1",
    )


def test_p8_v06_cancel_paid_returns_stock(tmp_path, settings):
    variant = stocked_variant(5)
    order = holding_order(variant, 2)
    inventory.commit_reservations(order)
    Order.objects.filter(pk=order.pk).update(
        state="paid",
        shipping_address=STAND_IN_ADDRESS,
        subtotal_cents=10000,
        total_cents=10000,
    )
    payment = PaymentFactory(order=order, status="approved", amount_cents=10000)
    item = StockItem.objects.get(variant=variant)
    assert item.on_hand == 3

    result = apply_event(
        order.pk, "cancelled_by_staff", actor="staff:1", cancel_reason="Sin stock"
    )

    assert result.state == "cancelled"
    item.refresh_from_db()
    assert (item.on_hand, item.reserved) == (5, 0)
    ledger = StockLedger.objects.get(order=order, reason="return")
    assert (ledger.delta, ledger.balance_after) == (2, 5)
    assert_stock_integrity(variant)
    refunds = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "mock_store" / "payments").glob("mock_ref_*.json")
    ]
    assert [(r["payment_id"], r["amount_cents"]) for r in refunds] == [
        (payment.pk, 10000)
    ]
    payment.refresh_from_db()
    assert (payment.refunded_cents, payment.status) == (10000, "refunded")
