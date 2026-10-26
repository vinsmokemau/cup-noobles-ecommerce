"""`expire_reservations` when one order cannot be moved (SPEC.md §4.8; T9.17 coverage gaps)."""

import logging
from datetime import timedelta

from django.core.management import call_command

from apps.inventory.management.commands import expire_reservations
from apps.inventory.models import InventoryReservation
from apps.orders.state_machine import IllegalTransition
from tests.factories.inventory import holding_order, stocked_variant


def test_an_order_that_cannot_be_expired_is_logged_and_the_others_still_expire(
    clock, db, caplog, monkeypatch
):
    clock.travel("2026-03-01T12:00:00Z")
    variant = stocked_variant(on_hand=5)
    stuck = holding_order(variant, 1, ttl=timedelta(hours=1))
    other = holding_order(variant, 1, ttl=timedelta(hours=1))
    clock.travel("2026-03-01T13:00:01Z")
    real = expire_reservations.expire_order

    def expire(order_id):
        if order_id == stuck.pk:
            raise IllegalTransition("paid", "deadline_passed")
        return real(order_id)

    monkeypatch.setattr(expire_reservations, "expire_order", expire)
    caplog.set_level(logging.ERROR)

    call_command("expire_reservations")

    assert InventoryReservation.objects.get(order=stuck).state == "held"
    assert InventoryReservation.objects.get(order=other).state == "released"
    assert f"Order {stuck.pk} could not be expired; left alone" in caplog.text
