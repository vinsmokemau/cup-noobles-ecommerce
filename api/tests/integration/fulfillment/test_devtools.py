"""The `mock_carrier` command and the carrier dev tools' absence in production (SPEC.md 10.12)."""

import importlib
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import clear_url_caches

from apps.orders.models import Order
from apps.shipping.carriers.base import ShipmentStatus
from apps.shipping.carriers.mock import MockCarrier
from tests.factories.orders import ShipmentFactory, order_in_state

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = StringIO()
    call_command("mock_carrier", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def shipped():
    order = order_in_state("shipped")
    shipment = ShipmentFactory(order=order, carrier="mock")
    MockCarrier().create_shipment(order, tracking_number=shipment.tracking_number)
    return order, shipment


def test_p10_v04_carrier_devtools_absent_in_prod(client, settings, shipped):
    import config.urls

    _, shipment = shipped
    # prod.py forces DEV_TOOLS_ENABLED to False whatever the environment says.
    settings.DEV_TOOLS_ENABLED = False
    clear_url_caches()
    importlib.reload(config.urls)
    try:
        page = client.get(f"/dev/carrier/track/{shipment.tracking_number}/")
        with pytest.raises(CommandError, match="DEV_TOOLS_ENABLED"):
            call_command(
                "mock_carrier", "advance", shipment.tracking_number, "--to", "delivered"
            )
    finally:
        settings.DEV_TOOLS_ENABLED = True
        clear_url_caches()
        importlib.reload(config.urls)

    assert page.status_code == 404
    assert (
        MockCarrier().get_status(shipment.tracking_number) is ShipmentStatus.IN_TRANSIT
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("in_transit", ShipmentStatus.IN_TRANSIT),
        ("delivered", ShipmentStatus.DELIVERED),
        ("exception", ShipmentStatus.EXCEPTION),
    ],
)
def test_advance_records_the_status_without_syncing(shipped, target, expected):
    order, shipment = shipped

    run("advance", shipment.tracking_number, "--to", target)

    assert MockCarrier().get_status(shipment.tracking_number) is expected
    assert Order.objects.get(pk=order.pk).state == "shipped"


def test_advance_with_sync_delivers_the_order_through_production_code(shipped):
    order, shipment = shipped

    out = run("advance", shipment.tracking_number, "--to", "delivered", "--sync")

    assert Order.objects.get(pk=order.pk).state == "delivered"
    assert "delivered 1" in out


def test_sync_only_touches_the_named_shipment(shipped):
    mine, shipment = shipped
    other = order_in_state("shipped")
    other_shipment = ShipmentFactory(order=other, carrier="mock")
    MockCarrier().create_shipment(other, tracking_number=other_shipment.tracking_number)
    MockCarrier().record_status(
        other_shipment.tracking_number, ShipmentStatus.DELIVERED
    )

    run("advance", shipment.tracking_number, "--to", "delivered", "--sync")

    assert Order.objects.get(pk=mine.pk).state == "delivered"
    assert Order.objects.get(pk=other.pk).state == "shipped"


def test_unknown_tracking_number_and_target_are_errors(shipped):
    with pytest.raises(CommandError, match="no shipment NO-EXISTE"):
        run("advance", "NO-EXISTE", "--to", "delivered")
    _, shipment = shipped
    with pytest.raises(CommandError):
        run("advance", shipment.tracking_number, "--to", "perdido")
