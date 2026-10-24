import pytest
from django.core.management import call_command

from apps.inventory.models import Location
from apps.shipping.models import MxState

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
