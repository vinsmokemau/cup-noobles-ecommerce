from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    rule,
    run_state_machine_as_test,
)

from apps.orders.models import Order
from apps.orders.state_machine import (
    TRANSITIONS,
    GuardFailed,
    IllegalTransition,
    apply_event,
)
from tests.factories.orders import ShipmentFactory, order_in_state
from tests.factories.payments import PaymentFactory

pytestmark = pytest.mark.django_db

EVENTS = sorted({event for _, event in TRANSITIONS})
REFUND_EVENTS = {"refund_issued", "partial_refund_issued"}
CLOSED = {"completed", "expired", "cancelled"}


class OrderMachine(RuleBasedStateMachine):
    """Random events, valid or not, against one order. Each example runs in a savepoint that is
    rolled back."""

    def __init__(self):
        super().__init__()
        self.savepoint = transaction.atomic()
        self.savepoint.__enter__()
        self.order = order_in_state("draft")
        self.payment = PaymentFactory(order=self.order, amount_cents=10000)
        self.expected_events = 0

    def teardown(self):
        transaction.set_rollback(True)
        self.savepoint.__exit__(None, None, None)

    @rule(
        event=st.sampled_from(EVENTS),
        amount=st.sampled_from([10000, 9999]),
        reason=st.sampled_from(["", "Sin stock"]),
        refunded=st.sampled_from([0, 4000, 10000]),
        deadline=st.sampled_from([-1, 1]),
    )
    def fire(self, event, amount, reason, refunded, deadline):
        Order.objects.filter(pk=self.order.pk).update(
            payment_deadline_at=timezone.now() + deadline * timedelta(hours=1)
        )
        before = Order.objects.get(pk=self.order.pk)
        try:
            after = apply_event(
                self.order.pk,
                event,
                amount_cents=amount,
                cancel_reason=reason,
                payment_id=self.payment.pk,
                refunded_cents=refunded,
            )
        except (IllegalTransition, GuardFailed):
            assert Order.objects.get(pk=self.order.pk).state == before.state
        else:
            self.expected_events += 1
            last = after.events.order_by("-id").first()
            assert (last.from_state, last.to_state, last.event) == (
                before.state,
                after.state,
                event,
            )
            # Refunds are payment records (G26, G27, ADR-0043): a partial refund, and any
            # refund after a close, keep the order state; a full refund before it ends in
            # `refunded`. The amount lands on the payment.
            if event == "partial_refund_issued" or before.state in CLOSED:
                assert after.state == before.state
            elif event == "refund_issued":
                assert after.state == "refunded"
            if event in REFUND_EVENTS:
                self.payment.refresh_from_db()
                assert self.payment.refunded_cents == refunded

    @rule()
    def add_shipment(self):
        # An order has at most one shipment (OA-60).
        if not self.order.shipments.exists():
            ShipmentFactory(order=self.order)

    @invariant()
    def one_event_row_per_legal_transition(self):
        assert self.order.events.count() == self.expected_events


# The `ci` profile runs 1000 examples of 25 steps, longer than the default 60 s limit.
@pytest.mark.timeout(900)
def test_p8_v05_one_event_row_per_transition():
    run_state_machine_as_test(
        OrderMachine, settings=settings(deadline=None, stateful_step_count=25)
    )
