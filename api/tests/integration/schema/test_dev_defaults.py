import pytest
from django.core.management import call_command

from apps.core.placeholders import placeholder_names
from apps.inventory.models import Location
from apps.shipping.models import (
    MxState,
    ShippingRate,
    ShippingZone,
    ShippingZoneState,
)

pytestmark = pytest.mark.django_db


def snapshot():
    return (
        list(MxState.objects.order_by("code").values_list("code", "name")),
        list(Location.objects.order_by("id").values()),
    )


def test_seed_dev_defaults_seeds_states_and_warehouse_once():
    call_command("seed_dev_defaults")
    first = snapshot()
    call_command("seed_dev_defaults")
    assert snapshot() == first

    states = dict(first[0])
    assert len(states) == 32
    assert {"CMX", "MEX", "JAL", "NLE", "YUC"} <= states.keys()
    assert all(len(code) == 3 for code in states)

    (warehouse,) = first[1]
    assert warehouse["code"] == "almacen"
    assert warehouse["name"] == "[PLACEHOLDER] Almacén Cup Noobles"
    assert warehouse["kind"] == "warehouse"
    assert warehouse["is_pickup_point"] is False


def test_seed_states_command_is_idempotent_and_leaves_the_warehouse_alone():
    call_command("seed_states")
    first = snapshot()
    call_command("seed_states")
    assert snapshot() == first
    assert len(first[0]) == 32
    assert first[1] == []


def test_seed_dev_defaults_seeds_the_d5_shipping_shape_once():
    def shipping():
        return (
            list(ShippingZone.objects.order_by("code").values()),
            list(ShippingZoneState.objects.order_by("state_id").values()),
            list(
                ShippingRate.objects.order_by(
                    "zone__code", "min_subtotal_cents"
                ).values()
            ),
        )

    call_command("seed_dev_defaults")
    first = shipping()
    call_command("seed_dev_defaults")
    assert shipping() == first

    zones = {zone.code: zone for zone in ShippingZone.objects.all()}
    assert set(zones) == {"local", "nacional"}

    zone_of = {
        link.state_id: link.zone.code
        for link in ShippingZoneState.objects.select_related("zone")
    }
    assert len(zone_of) == 32
    assert {code for code, zone in zone_of.items() if zone == "local"} == {"CMX", "MEX"}

    rows = {
        (rate.zone.code, rate.min_subtotal_cents): rate
        for rate in ShippingRate.objects.select_related("zone")
    }
    assert len(rows) == 4
    expected = {
        ("local", 0): (150_000, 9_900, 1, 3),
        ("local", 150_000): (None, 0, 1, 3),
        ("nacional", 0): (150_000, 17_900, 3, 7),
        ("nacional", 150_000): (None, 0, 3, 7),
    }
    for key, (max_cents, price, eta_min, eta_max) in expected.items():
        rate = rows[key]
        assert rate.name == "[PLACEHOLDER] Envío estándar"
        assert (rate.max_subtotal_cents, rate.price_cents) == (max_cents, price)
        assert (rate.eta_min_days, rate.eta_max_days) == (eta_min, eta_max)
        assert rate.is_active


def test_check_placeholders_flags_the_seeded_shipping_rows():
    call_command("seed_dev_defaults")
    findings = placeholder_names()
    assert sum(item.startswith("shipping_zone") for item in findings) == 2
    assert sum(item.startswith("shipping_rate") for item in findings) == 4
