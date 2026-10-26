"""Order admin (SPEC.md 8.A, T8.5, P8-V15)."""

import re

import pytest
from django.urls import reverse

from apps.orders.models import ORDER_STATES, Order
from apps.orders.state_machine import TRANSITIONS
from tests.factories.orders import OrderLineFactory, ShipmentFactory, order_in_state

pytestmark = pytest.mark.django_db

CHANGE = "admin:orders_order_change"
EVENT = "admin:orders_order_event"
CHANGELIST = "admin:orders_order_changelist"


def rendered_events(response):
    html = response.content.decode()
    return re.findall(r'<button type="submit" name="event" value="([a-z_0-9]+)"', html)


def fire(client, order, event, **fields):
    return client.post(
        reverse(EVENT, args=[order.pk]), {"event": event, **fields}, follow=True
    )


def note_form(**fields):
    """The change form as a browser posts it: the note plus the two inline management forms
    (an order with no lines and no events)."""
    management = {
        f"{prefix}-{name}": value
        for prefix in ("lines", "events")
        for name, value in (
            ("TOTAL_FORMS", "0"),
            ("INITIAL_FORMS", "0"),
            ("MIN_NUM_FORMS", "0"),
            ("MAX_NUM_FORMS", "1000"),
        )
    }
    return {**management, **fields}


def messages_of(response):
    return [str(message) for message in response.context["messages"]]


@pytest.mark.parametrize("state", ORDER_STATES)
def test_p8_v15_action_bar_legal_events_only(admin_client, state):
    order = order_in_state(state)

    page = admin_client.get(reverse(CHANGE, args=[order.pk]))

    legal = [event for source, event in TRANSITIONS if source == state]
    assert rendered_events(page) == legal


def test_p8_v15_illegal_event_shows_an_error_and_changes_nothing(admin_client):
    order = order_in_state("completed")

    response = fire(admin_client, order, "payment_approved", amount_cents=10000)

    assert messages_of(response) == [
        "Ese evento no es válido para el estado actual del pedido."
    ]
    order.refresh_from_db()
    assert order.state == "completed"
    assert not order.events.exists()


def test_p8_v15_legal_event_goes_through_apply_event(admin_client, admin_user):
    order = order_in_state("shipped")

    response = fire(admin_client, order, "marked_delivered")

    order.refresh_from_db()
    assert order.state == "delivered"
    event = order.events.get()
    assert (event.event, event.actor) == ("marked_delivered", f"staff:{admin_user.pk}")
    assert "delivered" in messages_of(response)[0]


def test_p8_v15_guard_failure_is_an_error_message(admin_client):
    order = order_in_state("preparing")

    response = fire(admin_client, order, "shipment_created")

    assert "no shipment with a tracking number" in messages_of(response)[0]
    order.refresh_from_db()
    assert order.state == "preparing"
    assert not order.events.exists()


def test_p8_v15_staff_cancel_needs_a_reason(admin_client):
    order = order_in_state("paid")
    page = admin_client.get(reverse(CHANGE, args=[order.pk]))
    assert 'name="cancel_reason"' in page.content.decode()

    fire(admin_client, order, "cancelled_by_staff", cancel_reason=" ")
    order.refresh_from_db()
    assert order.state == "paid"

    fire(admin_client, order, "cancelled_by_staff", cancel_reason="Sin stock")
    order.refresh_from_db()
    assert (order.state, order.cancel_reason) == ("cancelled", "Sin stock")


def test_p8_v15_shipment_button_works_once_a_shipment_exists(admin_client):
    order = order_in_state("preparing")
    ShipmentFactory(order=order)

    fire(admin_client, order, "shipment_created")

    order.refresh_from_db()
    assert order.state == "shipped"


def test_p8_v15_event_url_rejects_get(admin_client):
    order = order_in_state("shipped")

    response = admin_client.get(reverse(EVENT, args=[order.pk]))

    assert response.status_code == 403
    order.refresh_from_db()
    assert order.state == "shipped"


def test_p8_v15_state_is_not_editable_and_the_note_is(admin_client):
    order = order_in_state("paid")

    page = admin_client.get(reverse(CHANGE, args=[order.pk]))
    form = page.context["adminform"].form
    assert list(form.fields) == ["internal_note"]

    # A forged `state` in the body changes nothing; the note is saved.
    response = admin_client.post(
        reverse(CHANGE, args=[order.pk]),
        note_form(state="completed", total_cents=1, internal_note="Llamar al cliente"),
    )

    assert response.status_code == 302
    order.refresh_from_db()
    assert (order.state, order.total_cents, order.internal_note) == (
        "paid",
        10000,
        "Llamar al cliente",
    )
    assert not order.events.exists()


def test_saving_the_note_never_writes_a_stale_state(admin_client, monkeypatch):
    from django.contrib import admin

    order = order_in_state("paid")
    order_admin = admin.site._registry[Order]
    original = order_admin.get_object

    def stale_object(request, object_id, from_field=None):
        obj = original(request, object_id, from_field)
        # A transition commits after the page loaded the row and before the save.
        Order.objects.filter(pk=obj.pk).update(state="preparing")
        return obj

    monkeypatch.setattr(order_admin, "get_object", stale_object)
    admin_client.post(reverse(CHANGE, args=[order.pk]), note_form(internal_note="nota"))

    order.refresh_from_db()
    assert (order.state, order.internal_note) == ("preparing", "nota")


def test_lines_totals_and_timeline_are_shown_read_only(admin_client, admin_user, rf):
    from django.contrib import admin

    order = order_in_state("shipped", subtotal_cents=25050, total_cents=25050)
    OrderLineFactory(order=order, sku="TAZA-1", unit_price_cents=25050)
    fire(admin_client, order, "marked_delivered")

    page = admin_client.get(reverse(CHANGE, args=[order.pk]))
    html = page.content.decode()

    assert "TAZA-1" in html
    assert "$250.50 MXN" in html
    assert "marked_delivered" in html
    request = rf.get("/")
    request.user = admin_user
    model_admin = admin.site._registry[Order]
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_delete_permission(request)
    for inline in model_admin.get_inline_instances(request, order):
        assert not inline.has_add_permission(request, order)
        assert not inline.has_change_permission(request, order)
        assert not inline.has_delete_permission(request, order)


def test_changelist_filters_by_state(admin_client):
    paid = order_in_state("paid")
    order_in_state("completed")

    response = admin_client.get(reverse(CHANGELIST), {"state__exact": "paid"})

    assert [row.pk for row in response.context["cl"].result_list] == [paid.pk]
