"""Guard and edge cases of Phase 8 that no transition-table row reaches (coverage of the
critical scope, §0.2 ratchet)."""

import json

import pytest
from django.urls import reverse

from apps.inventory import services as inventory
from apps.inventory.models import StockLedger
from apps.orders.admin import format_money
from apps.orders.models import Order
from apps.orders.state_machine import (
    GuardFailed,
    _guard_target_complete,
    apply_event,
)
from apps.payments.mock import MockPaymentProvider
from tests.factories.inventory import holding_order, stocked_variant
from tests.factories.orders import OrderLineFactory, order_in_state
from tests.factories.payments import PaymentFactory

pytestmark = pytest.mark.django_db


def refused(order, event, **kwargs):
    state = order.state
    with pytest.raises(GuardFailed):
        apply_event(order.pk, event, **kwargs)
    order.refresh_from_db()
    assert order.state == state
    assert not order.events.exists()


def test_checkout_guard_refuses_a_draft_with_no_lines():
    refused(order_in_state("draft"), "checkout_submitted")


def test_checkout_guard_refuses_totals_that_are_not_the_recomputed_totals():
    order = order_in_state("draft")  # a total of 10000, but the line is worth 5000
    OrderLineFactory(
        order=order, variant=stocked_variant(5), quantity=1, unit_price_cents=5000
    )
    refused(order, "checkout_submitted")


def test_checkout_guard_refuses_a_line_that_is_out_of_stock():
    order = order_in_state("draft")
    OrderLineFactory(
        order=order, variant=stocked_variant(1), quantity=2, unit_price_cents=5000
    )
    refused(order, "checkout_submitted")


def test_pickup_target_needs_a_location():
    with pytest.raises(GuardFailed):
        _guard_target_complete(Order(fulfillment_method="pickup"))


def test_payment_is_refused_on_an_order_with_pre_order_lines():
    order = order_in_state("pending_payment", has_preorder_items=True)
    refused(order, "payment_approved", amount_cents=10000)


@pytest.mark.parametrize("event", ["refund_issued", "partial_refund_issued"])
def test_refund_needs_a_payment_of_this_order(event):
    order = order_in_state("paid")
    other = PaymentFactory(order=order_in_state("paid"), amount_cents=10000)
    refused(order, event, refunded_cents=4000)
    refused(order, event, payment_id=other.pk, refunded_cents=4000)


def test_return_stock_twice_returns_the_units_once():
    variant = stocked_variant(5)
    order = holding_order(variant, 2)
    inventory.commit_reservations(order)

    inventory.return_stock(order)
    inventory.return_stock(order)

    assert StockLedger.objects.filter(order=order, reason="return").count() == 1


def test_format_money_of_nothing_is_a_dash():
    assert format_money(None) == "—"


def test_admin_event_url_of_a_missing_order_is_forbidden(admin_client):
    response = admin_client.post(reverse("admin:orders_order_event", args=[999999]))
    assert response.status_code == 403


def test_admin_change_page_of_a_missing_order_redirects(admin_client):
    response = admin_client.get(reverse("admin:orders_order_change", args=[999999]))
    assert response.status_code == 302


def test_a_failed_mock_write_leaves_no_file_behind(settings, monkeypatch, tmp_path):
    settings.MOCK_STORE_DIR = str(tmp_path)

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", broken)
    with pytest.raises(OSError):
        MockPaymentProvider()._write("mock_ref_x", {"id": "x"})

    assert list((tmp_path / "payments").iterdir()) == []
