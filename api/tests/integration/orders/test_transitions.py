"""Every event the table does not allow is rejected and changes nothing (SPEC.md 8.A, T8.1)."""

from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import time_machine
from django.conf import settings

from apps.inventory import services
from apps.inventory.models import InventoryReservation, Location, StockLedger
from apps.notifications.models import EmailOutbox
from apps.orders.models import ORDER_STATES, Order, OrderEvent
from apps.orders.pricing import compute_totals
from apps.orders.state_machine import (
    TRANSITIONS,
    GuardFailed,
    IllegalTransition,
    apply_event,
)
from apps.payments.models import Payment
from tests.factories.inventory import stocked_variant
from tests.factories.orders import (
    STAND_IN_ADDRESS,
    DraftOrderFactory,
    OrderLineFactory,
    ShipmentFactory,
    order_in_state,
    order_through_checkout,
)

pytestmark = pytest.mark.django_db

EVENTS = sorted({event for _, event in TRANSITIONS})
ILLEGAL = [
    (state, event)
    for state in ORDER_STATES
    for event in EVENTS
    if (state, event) not in TRANSITIONS
]
TERMINAL = ["completed", "cancelled", "expired", "refunded"]


def snapshot(order):
    return (
        Order.objects.filter(pk=order.pk).values().get(),
        list(InventoryReservation.objects.filter(order=order).values()),
        list(OrderEvent.objects.filter(order=order).values_list("pk", flat=True)),
    )


@pytest.mark.parametrize(
    ("state", "event"), ILLEGAL, ids=[f"{state}-{event}" for state, event in ILLEGAL]
)
def test_p8_v07_every_illegal_event_rejected(state, event):
    order = order_in_state(state)
    services.reserve(order, [(stocked_variant(2), 1)], ttl=timedelta(hours=1))
    before = snapshot(order)
    with pytest.raises(IllegalTransition):
        apply_event(order.pk, event, cancel_reason="x", amount_cents=10000)
    assert snapshot(order) == before


def test_p8_v07_terminal_states_reject_every_event():
    assert {state for state, _ in ILLEGAL} == set(ORDER_STATES)
    for state in TERMINAL:
        assert {e for s, e in ILLEGAL if s == state} == set(EVENTS)


# --- P8-V01: one case per Release 1 row of 8.A ---------------------------------------------


def _draft_order():
    """A complete `draft` delivery order with one line of an in-stock variant (T1's source)."""
    variant = stocked_variant(5)
    totals = compute_totals([OrderLineFactory.build(unit_price_cents=10000)], 0, 0)
    order = DraftOrderFactory(
        shipping_address=STAND_IN_ADDRESS,
        subtotal_cents=totals.subtotal_cents,
        total_cents=totals.total_cents,
        tax_included_cents=totals.tax_included_cents,
    )
    OrderLineFactory(order=order, variant=variant, quantity=1, unit_price_cents=10000)
    return order


def _approve_payment(order):
    Payment.objects.filter(order=order).update(
        status="approved", provider_payment_id=f"mock_pay_{order.pk}"
    )
    return Payment.objects.get(order=order)


@dataclass
class Row:
    """One row of 8.A. `prepare(order, ok)` puts the order where a passing (`ok`) or a failing
    guard applies and returns the event kwargs. `check(before, after)` asserts the listed side
    effects. `pass_at` and `fail_at` move the clock, as an offset from `payment_deadline_at`.
    `fails=False` marks a row whose guard is "—"."""

    source: str
    event: str
    target: str
    check: Callable[[Order, Order], None]
    prepare: Callable[[Order, bool], dict[str, Any]] = lambda order, ok: {}
    pass_at: timedelta | None = None
    fail_at: timedelta | None = None
    fails: bool = True
    start: Callable[[], Order] | None = None


def _check_t1(before, after):
    assert after.payment_deadline_at > after.placed_at
    held = InventoryReservation.objects.filter(order=after, state="held")
    assert held.count() == after.lines.count() > 0
    payment = Payment.objects.get(order=after)
    assert (payment.status, payment.amount_cents) == ("initiated", after.total_cents)
    assert list(Path(settings.MOCK_STORE_DIR, "payments").glob("mock_pref_*.json"))
    assert payment.raw["checkout_url"].endswith(f"{payment.provider_preference_id}/")


def _prepare_t1(order, ok):
    if not ok:
        Order.objects.filter(pk=order.pk).update(shipping_address=None)
    return {}


def _check_t2(before, after):
    assert after.paid_at is not None
    assert not InventoryReservation.objects.filter(order=after, state="held").exists()
    assert StockLedger.objects.filter(order=after, reason="sale_online").exists()
    assert EmailOutbox.objects.filter(
        order=after, template="order_confirmation"
    ).exists()


def _prepare_t2(order, ok):
    return {"amount_cents": order.total_cents if ok else order.total_cents - 1}


def _check_t4(before, after):
    assert InventoryReservation.objects.filter(order=after, state="held").exists()


def _check_t5(before, after):
    assert not InventoryReservation.objects.filter(order=after, state="held").exists()
    assert InventoryReservation.objects.filter(order=after, state="released").exists()
    assert EmailOutbox.objects.filter(order=after, template="order_expired").exists()


def _check_t6(before, after):
    assert after.cancelled_at is not None
    assert InventoryReservation.objects.filter(order=after, state="released").exists()


def _prepare_t7(order, ok):
    if not ok:  # a pickup order (R2) is not a delivery order
        Order.objects.filter(pk=order.pk).update(
            fulfillment_method="pickup",
            pickup_location=Location.objects.first(),
            shipping_cents=0,
            total_cents=order.subtotal_cents,
        )
    return {}


def _prepare_t10(order, ok):
    if ok:
        ShipmentFactory(order=order)
    return {}


def _check_t10(before, after):
    assert after.shipped_at is not None
    assert EmailOutbox.objects.filter(order=after, template="order_shipped").exists()


def _check_t11(before, after):
    assert after.shipments.get().delivered_at is not None


def _check_t12(before, after):
    assert after.completed_at is not None


def _prepare_t16(order, ok):
    _approve_payment(order)
    return {"cancel_reason": "Sin existencias"} if ok else {}


def _check_t16(before, after):
    assert after.cancel_reason == "Sin existencias" and after.cancelled_at is not None
    assert StockLedger.objects.filter(order=after, reason="return").exists()
    payment = Payment.objects.get(order=after)
    assert (payment.status, payment.refunded_cents) == ("refunded", after.total_cents)
    assert list(Path(settings.MOCK_STORE_DIR, "payments").glob("mock_ref_*.json"))


def _prepare_t17(order, ok):
    payment = _approve_payment(order)
    amount = payment.amount_cents if ok else payment.amount_cents - 1
    return {"payment_id": payment.pk, "refunded_cents": amount}


def _check_t17(before, after):
    payment = Payment.objects.get(order=after)
    assert payment.refunded_cents == payment.amount_cents


def _prepare_t18(order, ok):
    payment = _approve_payment(order)
    amount = payment.amount_cents // 2 if ok else payment.amount_cents
    return {"payment_id": payment.pk, "refunded_cents": amount}


def _check_t18(before, after):
    payment = Payment.objects.get(order=after)
    assert 0 < payment.refunded_cents < payment.amount_cents


ROWS = {
    "T1": Row(
        "draft",
        "checkout_submitted",
        "pending_payment",
        _check_t1,
        _prepare_t1,
        start=_draft_order,
    ),
    "T2": Row("pending_payment", "payment_approved", "paid", _check_t2, _prepare_t2),
    "T4": Row(
        "pending_payment",
        "payment_rejected",
        "pending_payment",
        _check_t4,
        fail_at=timedelta(seconds=1),
    ),
    "T5": Row(
        "pending_payment",
        "deadline_passed",
        "expired",
        _check_t5,
        pass_at=timedelta(seconds=1),
    ),
    "T6": Row(
        "pending_payment", "cancelled_by_customer", "cancelled", _check_t6, fails=False
    ),
    "T7": Row("paid", "auto", "preparing", lambda b, a: None, _prepare_t7),
    "T10": Row("preparing", "shipment_created", "shipped", _check_t10, _prepare_t10),
    "T11": Row("shipped", "marked_delivered", "delivered", _check_t11, fails=False),
    "T12": Row("delivered", "auto_after_7d", "completed", _check_t12, fails=False),
    "T16-paid": Row(
        "paid", "cancelled_by_staff", "cancelled", _check_t16, _prepare_t16
    ),
    "T16-preparing": Row(
        "preparing", "cancelled_by_staff", "cancelled", _check_t16, _prepare_t16
    ),
    "T17": Row("paid", "refund_issued", "refunded", _check_t17, _prepare_t17),
    "T18": Row(
        "paid", "partial_refund_issued", "partially_refunded", _check_t18, _prepare_t18
    ),
}


def _start(row):
    return row.start() if row.start else order_through_checkout(row.source)


def _clock(order, offset):
    if offset is None:
        return nullcontext()
    return time_machine.travel(order.payment_deadline_at + offset, tick=False)


def test_p8_v01_every_r1_event_has_a_row():
    assert {row.event for row in ROWS.values()} == set(EVENTS)


@pytest.mark.parametrize("row_id", list(ROWS))
def test_p8_v01_transition_table(row_id, dev_defaults):
    row = ROWS[row_id]

    # A passing guard yields the target state, the side effects, and exactly one order_event.
    order = _start(row)
    assert order.state == row.source
    kwargs = row.prepare(order, True)
    events_before = order.events.count()
    with _clock(order, row.pass_at):
        after = apply_event(order.pk, row.event, actor="test", **kwargs)
    assert after.state == row.target
    row.check(order, after)
    assert order.events.count() == events_before + 1
    event = order.events.order_by("-pk").first()
    assert (event.from_state, event.to_state, event.event) == (
        row.source,
        row.target,
        row.event,
    )

    # A failing guard raises and leaves the order, its holds and its events unchanged.
    if not row.fails:
        return
    order = _start(row)
    kwargs = row.prepare(order, False)
    before = snapshot(order)
    with _clock(order, row.fail_at), pytest.raises(GuardFailed):
        apply_event(order.pk, row.event, actor="test", **kwargs)
    assert snapshot(order) == before
