from datetime import timedelta

import pytest
from django.db import transaction
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    rule,
    run_state_machine_as_test,
)

from apps.inventory import services
from apps.inventory.errors import AdjustmentBelowReserved, InsufficientStock
from tests.factories.inventory import (
    LocationFactory,
    assert_stock_integrity,
    stocked_variant,
)
from tests.factories.orders import DraftOrderFactory

pytestmark = pytest.mark.django_db

VARIANT_COUNT = 2


class InventoryMachine(RuleBasedStateMachine):
    """Random receipts, holds, commits, releases and adjustments; the invariants of §4.6 hold
    after every step. Each example runs in a savepoint that is rolled back."""

    def __init__(self):
        super().__init__()
        self.savepoint = transaction.atomic()
        self.savepoint.__enter__()
        self.location = LocationFactory()
        self.variants = [
            stocked_variant(0, location=self.location) for _ in range(VARIANT_COUNT)
        ]
        self.open_orders = []

    def teardown(self):
        transaction.set_rollback(True)
        self.savepoint.__exit__(None, None, None)

    variant_index = st.integers(0, VARIANT_COUNT - 1)

    @rule(index=variant_index, qty=st.integers(1, 6))
    def receive(self, index, qty):
        services.receive_stock(self.variants[index], self.location, qty)

    @rule(index=variant_index, qty=st.integers(1, 6))
    def reserve(self, index, qty):
        order = DraftOrderFactory()
        try:
            services.reserve(
                order, [(self.variants[index], qty)], ttl=timedelta(hours=1)
            )
        except InsufficientStock:
            return
        self.open_orders.append(order)

    @rule(data=st.data())
    def commit(self, data):
        if self.open_orders:
            services.commit_reservations(data.draw(st.sampled_from(self.open_orders)))

    @rule(data=st.data())
    def release(self, data):
        if self.open_orders:
            order = data.draw(st.sampled_from(self.open_orders))
            services.release_reservations(order, reason="test")

    @rule(index=variant_index, delta=st.integers(-6, 6).filter(bool))
    def adjust(self, index, delta):
        try:
            services.adjust_stock(
                self.variants[index],
                self.location,
                delta,
                reason="adjustment",
                actor=None,
                note="",
            )
        except AdjustmentBelowReserved:
            pass

    @invariant()
    def ledger_and_reservations_agree_with_the_stock_row(self):
        for variant in self.variants:
            assert_stock_integrity(variant)


def test_p4_v06_ledger_sum_equals_on_hand():
    run_state_machine_as_test(
        InventoryMachine, settings=settings(deadline=None, stateful_step_count=25)
    )
