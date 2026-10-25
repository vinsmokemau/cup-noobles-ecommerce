"""Every event the table does not allow is rejected and changes nothing (SPEC.md 8.A, T8.1)."""

from datetime import timedelta

import pytest

from apps.inventory import services
from apps.inventory.models import InventoryReservation
from apps.orders.models import ORDER_STATES, Order, OrderEvent
from apps.orders.state_machine import TRANSITIONS, IllegalTransition, apply_event
from tests.factories.inventory import stocked_variant
from tests.factories.orders import order_in_state

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
