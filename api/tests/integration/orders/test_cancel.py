"""Staff cancellation (SPEC.md 8.A T16, T8.1)."""

import pytest

from apps.orders.state_machine import GuardFailed, apply_event
from tests.factories.orders import order_in_state

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
